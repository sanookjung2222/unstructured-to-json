from fastapi import FastAPI, Header, HTTPException, Depends, Request
from pydantic import BaseModel
from typing import List, Optional, Any, Dict
import anthropic
import openai
import time
import json
import re

# คงการดึง Database ของคุณไว้เหมือนเดิม
from database import get_user_by_app_key

# ==========================================
# 1) ตั้งค่าแอป FastAPI และสร้างหน้า Tutorial แบบ Dropdown
# ==========================================
api_description = """
**Headless API Engine สำหรับเชื่อมต่อ Make/Zapier**

---

<details>
<summary><b>🔽 🇹🇭 คู่มือการใช้งาน API (5 ขั้นตอน) (คลิกเพื่อเปิด)</b></summary>

<br>

**1. สร้างและคัดลอก App API Key:**
เข้าไปที่หน้าเว็บแอปพลิเคชันหลัก กดปุ่ม "⚡ Generate App API Key" แล้วคัดลอกรหัส

**2. เตรียม AI API Key (เลือกอย่างใดอย่างหนึ่ง หรือส่งมาทั้งคู่):**
* OpenAI API Key (ขึ้นต้นด้วย `sk-proj-...` หรือ `sk-...`)
* Anthropic API Key (ขึ้นต้นด้วย `sk-ant-...`)

**3. ตั้งค่า URL และ Method (ใน Make / Zapier / Postman):**
* URL: `http://127.0.0.1:8000/v1/extract`
* Method: `POST`

**4. กำหนด Headers และ Request Body:**

    [Headers]
    X-App-Key: sk_live_xxxxxxxxxxxxxxxx
    X-OpenAI-Key: sk-proj-xxxxxxxxxxxxxxxx (หากใช้ OpenAI)
    X-Anthropic-Key: sk-ant-xxxxxxxxxxxxxxxx (หากใช้ Anthropic)
    Content-Type: application/json

    [Body JSON]
    {
      "text": "ประชุมวันนี้ ตกลงเลื่อนวันเปิดตัวสินค้าไปเดือนหน้า และให้คุณเอทำรายงานส่งวันศุกร์",
      "lang": "TH",
      "fields": [
        {"name": "Summary", "desc": "สรุปเนื้อหาสำคัญ"},
        {"name": "Action_Item", "desc": "สิ่งที่ต้องทำและผู้รับผิดชอบ"}
      ]
    }

**5. ยิง Request และรับผลลัพธ์ (Response):**
เมื่อสำเร็จ ระบบจะส่ง Code 200 พร้อมผลลัพธ์แบบนี้:

    {
      "success": true,
      "provider": "openai",
      "data": [
        {
          "Summary": "เลื่อนวันเปิดตัวสินค้าเป็นเดือนหน้า",
          "Action_Item": "คุณเอต้องทำรายงานส่งวันศุกร์"
        }
      ],
      "processing_time_seconds": 2.45
    }

</details>
"""

app = FastAPI(
    title="Text Extractor API",
    description=api_description,
    version="1.2.0"
)

# ==========================================
# 2) กำหนดโครงสร้างข้อมูล (Pydantic Models)
# ==========================================
class ExtractRequest(BaseModel):
    text: str
    fields: List[Any]  # อัปเกรดเป็น List[Any] เพื่อรองรับรูปแบบ JSON จาก Zapier ป้องกัน Error 422
    lang: str = "TH"

class ExtractResponse(BaseModel):
    success: bool
    provider: str      # เพิ่มฟิลด์บอกว่าใช้ AI เจ้าไหน
    data: List[Dict[str, Any]]
    processing_time_seconds: float

# ==========================================
# 3) ฟังก์ชันสำหรับตรวจสอบ Key (Multi-AI Auth)
# ==========================================
def verify_keys(
    x_app_key: str = Header(..., alias="X-App-Key"),
    x_anthropic_key: Optional[str] = Header(None, alias="X-Anthropic-Key"),
    x_openai_key: Optional[str] = Header(None, alias="X-OpenAI-Key")
):
    # ตรวจสอบ App Key พื้นฐานจาก Database
    if not x_app_key.startswith("sk_live_"):
        raise HTTPException(status_code=401, detail="Invalid App API Key format")
    
    user = get_user_by_app_key(x_app_key)
    if not user:
         raise HTTPException(status_code=401, detail="Invalid or Revoked App API Key")
    
    # บังคับว่าต้องส่ง Key ของ AI เจ้าใดเจ้าหนึ่งมา
    if not x_anthropic_key and not x_openai_key:
        raise HTTPException(status_code=401, detail="Provide either X-OpenAI-Key or X-Anthropic-Key in Headers")
        
    return {
        "app_key": x_app_key, 
        "anthropic_key": x_anthropic_key,
        "openai_key": x_openai_key
    }

# ==========================================
# 4) ฟังก์ชันจัดการ Prompt และ JSON (ย้ายมาไว้ในนี้เพื่อให้ทำงานอิสระและเสถียรที่สุด)
# ==========================================
def parse_json_array(raw_output: str):
    cleaned = raw_output.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    data = json.loads(cleaned.strip())
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        raise ValueError("Expected a JSON array")
    return data

# ==========================================
# 5) เส้นทางหลักรับ Request (Endpoint)
# ==========================================
@app.post("/v1/extract", response_model=ExtractResponse)
def extract_data(
    req: ExtractRequest,
    keys: dict = Depends(verify_keys)
):
    start_time = time.time()
    anthropic_key = keys["anthropic_key"]
    openai_key = keys["openai_key"]
    
    # 5.1 เตรียม Prompt (ดึงตรรกะนี้มาไว้ในไฟล์นี้เพื่อรับมือ List[Any] ของ Zapier)
    processed_fields = []
    field_names = []
    for f in req.fields:
        if isinstance(f, dict):
            name = f.get("name", "")
            desc = f.get("desc", f"the value for {name}")
        else:
            name = getattr(f, "name", str(f))
            desc = getattr(f, "desc", f"the value for {name}")
        field_names.append(name)
        processed_fields.append(f'- "{name}": {desc}')
    
    field_block = "\n".join(processed_fields)
    
    prompt_text = f"""You are a precise data-extraction engine. Read the raw text below and extract the requested fields.
Rules:
- Return ONLY a valid JSON array of objects. No markdown formatting, no code fences.
- Each object must contain exactly these keys: {field_names}
- If the raw text describes multiple distinct items, return one object per item.
- If it describes only one item, return an array containing exactly one object.
- If a field's value cannot be found, use an empty string "".

Fields to extract:
{field_block}

Raw text:
\"\"\"
{req.text}
\"\"\"

Respond with the JSON array only."""

    if req.lang == "TH":
        prompt_text += "\n\nCRITICAL: You must extract and write the values in THAI language."
    else:
        prompt_text += "\n\nCRITICAL: You must extract and write the values in ENGLISH language."

    try:
        raw_output = ""
        provider_used = ""

        # 5.2 รันโมเดล (ถ้าส่ง OpenAI มา จะให้ความสำคัญกับ OpenAI ก่อน)
        if openai_key:
            client = openai.OpenAI(api_key=openai_key)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt_text}],
                temperature=0.0
            )
            raw_output = response.choices[0].message.content
            provider_used = "openai"
            
        elif anthropic_key:
            client = anthropic.Anthropic(api_key=anthropic_key)
            message = client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=2000,
                temperature=0,
                system="You are an expert data extraction bot. You only return valid JSON arrays.",
                messages=[{"role": "user", "content": prompt_text}]
            )
            raw_output = "".join(block.text for block in message.content if getattr(block, "type", "") == "text")
            provider_used = "anthropic"
        
        json_data = parse_json_array(raw_output)
        process_time = round(time.time() - start_time, 2)
        
        return ExtractResponse(
            success=True,
            provider=provider_used,
            data=json_data,
            processing_time_seconds=process_time
        )
        
    except openai.AuthenticationError:
        raise HTTPException(status_code=401, detail="OpenAI API Key is invalid or expired.")
    except anthropic.AuthenticationError:
        raise HTTPException(status_code=401, detail="Anthropic API Key is invalid or expired.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# 6) เส้นทางสำหรับ Debug (ตรวจสอบข้อมูลดิบจาก Zapier/Make)
# ==========================================
@app.post("/v1/debug")
async def debug_zapier(request: Request):
    body = await request.body()
    print("\n=== RAW DATA FROM ZAPIER ===")
    print(body.decode('utf-8'))
    print("============================\n")
    return {"status": "received"}


@app.get("/v1/check-keys")
def check_keys():
    from database import get_db_connection
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT app_api_key, is_pro FROM users")
    rows = cursor.fetchall()
    conn.close()
    return {"saved_keys_in_system": [dict(r) for r in rows]}

from pydantic import BaseModel
import secrets

class KeyActionRequest(BaseModel):
    license_key: str

import secrets
from database import save_app_api_key, revoke_app_api_key

# Endpoint ให้หน้าเว็บยิงคำสั่งมาสั่งสร้าง Key
@app.post("/v1/system/generate-key")
async def api_generate_key(request: Request):
    data = await request.json()
    lic_key = data.get("license_key", "dev_local")
    new_key = "sk_live_" + secrets.token_hex(16)
    
    save_app_api_key(lic_key, new_key) # FastAPI เป็นคนเซฟเอง
    return {"app_api_key": new_key}

# Endpoint ให้หน้าเว็บยิงคำสั่งมาลบ Key
@app.post("/v1/system/revoke-key")
async def api_revoke_key(request: Request):
    data = await request.json()
    lic_key = data.get("license_key", "dev_local")
    
    revoke_app_api_key(lic_key)
    return {"success": True}
