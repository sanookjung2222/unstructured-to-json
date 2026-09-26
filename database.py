import os
from supabase import create_client, Client

# ใส่ URL และ Anon Key ที่ได้มาจากหน้า Dashboard ของ Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://dfwdqkxqsegszjovhsia.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRmd2Rxa3hxc2Vnc3pqb3Zoc2lhIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTA0MDQ3MDEsImV4cCI6MjEwNTk4MDcwMX0.Txsz2Mlhq-tmL5rATiC4K-VQmHzNpI13-QKFOI2q0a0")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def save_app_api_key(license_key: str, app_api_key: str):
    """บันทึกหรืออัปเดต App API Key ตาม License Key ลง Supabase"""
    data = {
        "license_key": license_key,
        "app_api_key": app_api_key,
        "is_pro": True
    }
    # ใช้ upsert เพื่อบันทึกใหม่ หรือทับของเดิมถ้ามี license_key นี้อยู่แล้ว
    supabase.table("users").upsert(data).execute()

def get_user_by_app_key(app_api_key: str):
    """ดึงข้อมูลผู้ใช้จาก App API Key (ใช้ใน api.py เช็กสิทธิ์)"""
    response = supabase.table("users").select("*").eq("app_api_key", app_api_key).eq("is_pro", True).execute()
    return response.data[0] if response.data else None

def get_app_key_by_license(license_key: str):
    """ดึง App API Key กลับมาเมื่อผู้ใช้ใส่ License Key ถูกต้อง"""
    response = supabase.table("users").select("app_api_key").eq("license_key", license_key).execute()
    if response.data and response.data[0].get("app_api_key"):
        return response.data[0]["app_api_key"]
    return None

def revoke_app_api_key(license_key: str):
    """ลบ App API Key เมื่อผู้ใช้กด Revoke"""
    supabase.table("users").update({"app_api_key": None}).eq("license_key", license_key).execute()
