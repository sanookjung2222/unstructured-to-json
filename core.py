import json
import re
import time
import anthropic

def build_extraction_prompt(fields, raw_text: str, lang: str = "TH") -> str:
    """
    สร้าง Prompt สำหรับส่งให้ Claude
    รองรับทั้งข้อมูลแบบ Dict (จาก app.py) และ Pydantic Model (จาก api.py)
    """
    lines = []
    field_names = []
    
    for f in fields:
        if isinstance(f, dict):
            name = f.get("name")
            desc = f.get("desc_th" if lang == "TH" else "desc_en", f.get("desc", ""))
        else:
            name = getattr(f, "name")
            desc = getattr(f, "desc", "")
            
        if not desc:
            desc = f"the value for {name}"
            
        lines.append(f'- "{name}": {desc}')
        field_names.append(name)
    
    field_block = "\n".join(lines)
    
    prompt_text = f"""You are a precise data-extraction engine. Read the raw text below and extract the requested fields.

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

    # บังคับภาษาตามที่ผู้ใช้เลือกบนหน้าเว็บ
    if lang == "TH":
        prompt_text += "\n\nCRITICAL: You must extract and write the values in THAI language."
    else:
        prompt_text += "\n\nCRITICAL: You must extract and write the values in ENGLISH language."

    return prompt_text

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

def call_claude_extract(api_key: str, fields: list, raw_text: str, lang: str = "TH"):
    """ฟังก์ชันหลักสำหรับเรียก AI ประมวลผลจากฝั่งหน้าเว็บ (Streamlit)"""
    start_time = time.time()
    prompt_text = build_extraction_prompt(fields, raw_text, lang)
    
    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model="claude-3-haiku-20240307",
        max_tokens=2000,
        temperature=0,
        system="You are an expert data extraction bot. You only return valid JSON arrays.",
        messages=[{"role": "user", "content": prompt_text}]
    )
    
    raw_output = "".join(block.text for block in message.content if getattr(block, "type", "") == "text")
    elapsed = time.time() - start_time
    return raw_output, elapsed
