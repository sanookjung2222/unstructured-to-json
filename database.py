import os
from supabase import create_client, Client

# ดึงค่าจาก Environment Variables เท่านั้น (ห้ามแปะคีย์จริงตรงนี้เด็ดขาด!)
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

# ตรวจสอบว่ามีการตั้งค่า Key หรือยัง
if not SUPABASE_URL or not SUPABASE_KEY:
    print("Warning: Supabase URL or Key is missing from Environment Variables.")

# สร้างการเชื่อมต่อเมื่อมี Key
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None

def save_app_api_key(license_key: str, app_api_key: str):
    """บันทึกหรืออัปเดต App API Key ตาม License Key ลง Supabase"""
    if not supabase: return
    data = {
        "license_key": license_key,
        "app_api_key": app_api_key,
        "is_pro": True
    }
    supabase.table("users").upsert(data).execute()

def get_user_by_app_key(app_api_key: str):
    """ดึงข้อมูลผู้ใช้จาก App API Key (ใช้ใน api.py เช็กสิทธิ์)"""
    if not supabase: return None
    response = supabase.table("users").select("*").eq("app_api_key", app_api_key).eq("is_pro", True).execute()
    return response.data[0] if response.data else None

def get_app_key_by_license(license_key: str):
    """ดึง App API Key กลับมาเมื่อผู้ใช้ใส่ License Key ถูกต้อง"""
    if not supabase: return None
    response = supabase.table("users").select("app_api_key").eq("license_key", license_key).execute()
    if response.data and response.data[0].get("app_api_key"):
        return response.data[0]["app_api_key"]
    return None

def revoke_app_api_key(license_key: str):
    """ลบ App API Key เมื่อผู้ใช้กด Revoke"""
    if not supabase: return
    supabase.table("users").update({"app_api_key": None}).eq("license_key", license_key).execute()
