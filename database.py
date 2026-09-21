import sqlite3
import os

DB_PATH = "app_data.db"

def get_db_connection():
    """เชื่อมต่อกับไฟล์ SQLite"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """สร้างตาราง users อัตโนมัติถ้ายังไม่มี"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            license_key TEXT PRIMARY KEY,
            app_api_key TEXT UNIQUE,
            is_pro INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def save_app_api_key(license_key: str, app_api_key: str):
    """บันทึกหรืออัปเดต App API Key ตาม License Key"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO users (license_key, app_api_key, is_pro)
        VALUES (?, ?, 1)
        ON CONFLICT(license_key) DO UPDATE SET app_api_key = excluded.app_api_key
    """, (license_key, app_api_key))
    conn.commit()
    conn.close()

def get_user_by_app_key(app_api_key: str):
    """ดึงข้อมูลผู้ใช้จาก App API Key (ใช้ใน api.py เช็กสิทธิ์)"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE app_api_key = ? AND is_pro = 1", (app_api_key,))
    user = cursor.fetchone()
    conn.close()
    return user

def revoke_app_api_key(license_key: str):
    """ลบ App API Key เมื่อผู้ใช้กด Revoke"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET app_api_key = NULL WHERE license_key = ?", (license_key,))
    conn.commit()
    conn.close()

# เรียกสร้าง Table ทันทีที่ import ไฟล์นี้
init_db()
def get_app_key_by_license(license_key: str):
    """ดึง App API Key กลับมาเมื่อผู้ใช้ใส่ License Key ถูกต้อง"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT app_api_key FROM users WHERE license_key = ?", (license_key,))
    row = cursor.fetchone()
    conn.close()
    return row["app_api_key"] if row else None
