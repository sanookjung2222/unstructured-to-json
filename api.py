from database import get_user_by_app_key
import time
import json
import re
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import anthropic

# ==========================================
# 1) ตั้งค่าแอป FastAPI
# ==========================================
app = FastAPI(
    title="Text Extractor API",
    description="Headless API Engine สำหรับเชื่อมต่อ Make/Zapier",
    version="1.0.0"
)

DEFAULT_MODEL = "claude-haiku-4-5"

# ==========================================
# 2) กำหนดโครงสร้างข้อมูลที่รับเข้ามา (Pydantic Models)
# ==========================================
class FieldDef(BaseModel):
    name: str
    desc: str = ""

class ExtractionRequest(BaseModel):
    text: str
    lang: str = "TH"
    fields: List[FieldDef]

# ==========================================
# 3) ฟังก์ชัน Core Logic
# ==========================================
def build_extraction_prompt(fields: List[FieldDef], raw_text: str) -> str:
    lines = []
    for f in fields:
        desc = f.desc if f.desc else f"the value for {f.name}"
        lines.append(f'- "{f.name}": {desc}')
    
    field_block = "\n".join(lines)
    field_names = [f.name for f in fields]
    
    return f"""You are a precise data-extraction engine. Read the raw text below and extract the requested fields.

Rules:
- Return ONLY a valid JSON array of objects. No markdown formatting, no code fences.
- Each object must contain exactly these keys: {field_names}
- If the raw text clearly describes multiple distinct items/records, return one object per item.
- If it describes only one item, return an array containing exactly one object.
- If a field's value cannot be found in the text, use an empty string "".

Fields to extract:
{field_block}

Raw text:
\"\"\"
{raw_text}
\"\"\"

Respond with the JSON array only."""

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
# 4) Endpoint หลักสำหรับรับ Webhook (POST /v1/extract)
# ==========================================
@app.post("/v1/extract")
async def extract_data(
    request: ExtractionRequest,
    x_app_key: Optional[str] = Header(None, alias="X-App-Key"),
    x_anthropic_key: Optional[str] = Header(None, alias="X-Anthropic-Key")
):
    if not x_app_key:
        raise HTTPException(status_code=401, detail="Missing X-App-Key (App API Key is required)")
    
    if not x_anthropic_key:
        raise HTTPException(status_code=401, detail="Missing X-Anthropic-Key (BYOK is required)")

    user = get_user_by_app_key(x_app_key)
if not user:
    raise HTTPException(status_code=401, detail="Invalid or Revoked App API Key")

    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")
    
    if not request.fields:
        raise HTTPException(status_code=400, detail="Fields cannot be empty")

    client = anthropic.Anthropic(api_key=x_anthropic_key)
    prompt = build_extraction_prompt(request.fields, request.text)

    try:
        start = time.time()
        message = client.messages.create(
            model=DEFAULT_MODEL,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}]
        )
        elapsed = time.time() - start
        
        raw_output = "".join(block.text for block in message.content if getattr(block, "type", "") == "text")
        records = parse_json_array(raw_output)
        
        return {
            "success": True,
            "data": records,
            "processing_time_seconds": round(elapsed, 2)
        }

    except anthropic.AuthenticationError:
        raise HTTPException(status_code=401, detail="Invalid Anthropic API Key")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")