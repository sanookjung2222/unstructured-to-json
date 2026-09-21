import json
import re

def build_extraction_prompt(fields, raw_text: str) -> str:
    """
    สร้าง Prompt สำหรับส่งให้ Claude
    รองรับทั้งข้อมูลแบบ Dict (จาก app.py) และ Pydantic Model (จาก api.py)
    """
    lines = []
    field_names = []
    
    for f in fields:
        # เช็กว่าเป็น Dict (หน้าเว็บ) หรือ Object (API)
        if isinstance(f, dict):
            name = f.get("name")
            desc = f.get("desc", f"the value for {name}")
        else:
            name = getattr(f, "name")
            desc = getattr(f, "desc", "") or f"the value for {name}"
            
        lines.append(f'- "{name}": {desc}')
        field_names.append(name)
    
    field_block = "\n".join(lines)
    
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
    """ทำความสะอาดและแปลงผลลัพธ์จาก AI เป็น JSON (List)"""
    cleaned = raw_output.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    data = json.loads(cleaned.strip())
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        raise ValueError("Expected a JSON array")
    return data