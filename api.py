import time
import json
import re
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import openai
from database import get_user_by_app_key
from core import build_extraction_prompt, parse_json_array

# ==========================================
# 1) ตั้งค่าแอป FastAPI
# ==========================================
app = FastAPI(
    title="Text Extractor API",
    description="Headless API Engine สำหรับเชื่อมต่อ Make/Zapier",
    version="1.0.0"
)

# ใช้โมเดลตัวเล็กที่ฉลาดและคุ้มค่าที่สุดของ OpenAI
DEFAULT_MODEL = "gpt-4o-mini"

# ==========================================
# 2) กำหนดโครงสร้างข้อมูลที่รับเข้ามา
# ==========================================
class FieldDef(BaseModel):
    name: str
    desc: str = ""

class ExtractionRequest(BaseModel):
    text: str
    lang: str = "TH"
    fields: List[FieldDef]


# ==========================================
# 4) Endpoint หลัก (POST /v1/extract)
# ==========================================
@app.post("/v1/extract")
async def extract_data(
    request: ExtractionRequest,
    x_app_key: Optional[str] = Header(None, alias="X-App-Key"),
    x_openai_key: Optional[str] = Header(None, alias="X-OpenAI-Key") # เปลี่ยนชื่อ Header เป็น OpenAI
):
    if not x_app_key:
        raise HTTPException(status_code=401, detail="Missing X-App-Key")
    
    if not x_openai_key:
        raise HTTPException(status_code=401, detail="Missing X-OpenAI-Key (OpenAI API Key is required)")

    # เช็กกับ Database จริง
    user = get_user_by_app_key(x_app_key)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or Revoked App API Key")

    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")
    
    if not request.fields:
        raise HTTPException(status_code=400, detail="Fields cannot be empty")

    # เรียกใช้งาน OpenAI API
    client = openai.OpenAI(api_key=x_openai_key)
    prompt = build_extraction_prompt(request.fields, request.text)

    try:
        start = time.time()
        response = client.chat.completions.create(
            model=DEFAULT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0 # ตั้งค่าเป็น 0 เพื่อให้ผลลัพธ์เป็นตรรกะตายตัวที่สุด
        )
        elapsed = time.time() - start
        
        raw_output = response.choices[0].message.content
        records = parse_json_array(raw_output)
        
        return {
            "success": True,
            "data": records,
            "processing_time_seconds": round(elapsed, 2)
        }

    except openai.AuthenticationError:
        raise HTTPException(status_code=401, detail="Invalid OpenAI API Key")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")
