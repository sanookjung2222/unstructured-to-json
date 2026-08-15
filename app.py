# -*- coding: utf-8 -*-
"""
Text Extractor — MVP (Single-file Streamlit app)
=================================================

วิธี Deploy บน Hugging Face Spaces:
1. สร้าง Space ใหม่ -> เลือก SDK เป็น "Streamlit"
2. อัปโหลดไฟล์นี้ (app.py) และ requirements.txt ไปไว้ที่ root ของ repo
3. (ไม่บังคับ แต่แนะนำ) ไปที่ Settings > Repository secrets ของ Space
   แล้วเพิ่มตัวแปร GUMROAD_PRODUCT_ID เพื่อให้ปุ่ม "Activate Pro"
   ตรวจสอบ License Key กับ Gumroad ได้จริง (หา product_id ได้จากหน้า
   Edit product บน Gumroad)
4. ผู้ใช้แต่ละคนใส่ Anthropic API Key ของตัวเอง (BYOK - Bring Your Own Key)
   แอปนี้แค่ส่ง key ที่ผู้ใช้กรอกไปเรียก Anthropic โดยตรงในแต่ละ request
   ไม่ได้บันทึกหรือส่งต่อไปที่อื่น และไม่ได้เก็บไว้ถาวร (หายไปเมื่อปิดแท็บ)

ข้อจำกัดของ MVP เวอร์ชันนี้ (ตั้งใจให้เรียบง่ายก่อน ค่อยอัปเกรดทีหลัง):
- ยังไม่มีฐานข้อมูล -> สถานะ Pro และ Custom Schema จะรีเซ็ตทุกครั้งที่ผู้ใช้
  โหลดหน้าเว็บใหม่ (ต้องกรอก License Key ใหม่)
- Mock/Sample response เป็นข้อมูลจำลองที่เขียนไว้ล่วงหน้า ไม่ได้เรียก AI จริง
"""

import streamlit as st
import secrets
import anthropic
import pandas as pd
import requests
import json
import re
import time
import os
import html


# ============================================================
# 1) ตั้งค่าเริ่มต้นของหน้าเว็บ (PAGE CONFIG)
# ============================================================

st.set_page_config(
    page_title="Text Extractor — Messy Text to Structured Data",
    page_icon="⚡",
    layout="wide",
)


# ============================================================
# 2) ธีมสี ฟอนต์ และ CSS (DESIGN SYSTEM)
# ============================================================
# แก้สีหรือฟอนต์ได้ที่ตัวแปร :root ด้านล่างนี้จุดเดียว ระบบจะเปลี่ยนทั้งแอป

CUSTOM_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
  --ink: #1B1F2B;
  --paper: #FAFAF9;
  --card: #FFFFFF;
  --accent: #F2A93B;
  --accent-ink: #1B1F2B;
  --muted: #6B7280;
  --border: #E7E2D6;
  --success: #1E9E6D;
  --danger: #D9483C;
  --locked: #9CA3AF;
}

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.stApp { background-color: var(--paper) !important; }
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }

h1, h2, h3, h4, .logo-title, .zone-title {
  font-family: 'Space Grotesk', sans-serif !important;
  color: var(--ink) !important;
}

code, pre, [data-testid="stCodeBlock"] {
  font-family: 'JetBrains Mono', monospace !important;
}

.logo-title { font-size: 1.5rem; font-weight: 700; color: var(--ink) !important; padding-top: 0.4rem; }

.hero-banner {
  background: linear-gradient(135deg, var(--ink) 0%, #2A2F3F 100%);
  padding: 1.4rem 1.8rem;
  border-radius: 14px;
  margin: 0.6rem 0 1.4rem 0;
  border-left: 5px solid var(--accent);
}
.hero-headline {
  color: #FAFAF9 !important;
  font-family: 'Space Grotesk', sans-serif !important;
  font-size: 1.25rem;
  font-weight: 700;
  line-height: 1.4;
}
.hero-pain {
  color: #A9ADBA !important;
  font-size: 0.85rem;
  font-style: italic;
  font-weight: 400;
  margin-bottom: 0.45rem;
  line-height: 1.4;
}
.hero-subheadline {
  color: #C9CCD6 !important;
  font-size: 0.95rem;
  font-weight: 400;
  margin-top: 0.5rem;
  line-height: 1.5;
}

.zone-title {
  font-size: 1.05rem;
  font-weight: 700;
  letter-spacing: 0.02em;
  margin: 1.6rem 0 0.6rem 0;
  padding-bottom: 0.4rem;
  border-bottom: 2px solid var(--border);
}

.schema-card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 0.9rem 1.1rem;
}
.field-row {
  display: flex;
  align-items: center;
  gap: 0.7rem;
  padding: 0.45rem 0;
  border-bottom: 1px dashed var(--border);
}
.field-row:last-child { border-bottom: none; }
.field-chip {
  font-family: 'JetBrains Mono', monospace;
  background: #FFF3DE;
  color: #8A5A00 !important;
  border-radius: 6px;
  padding: 0.15rem 0.55rem;
  font-size: 0.82rem;
  font-weight: 600;
  white-space: nowrap;
}
.field-desc { color: var(--muted) !important; font-size: 0.88rem; }

.locked-card {
  background: #F4F4F5;
  border: 1.5px dashed var(--locked);
  border-radius: 12px;
  padding: 1.1rem 1.3rem;
}
.locked-title { font-weight: 700; color: var(--ink) !important; margin-bottom: 0.3rem; }
.locked-desc { color: var(--muted) !important; font-size: 0.9rem; }

.pro-badge {
  display: inline-block;
  background: var(--accent);
  color: var(--accent-ink) !important;
  font-weight: 700;
  padding: 0.25rem 0.7rem;
  border-radius: 999px;
  font-size: 0.85rem;
  margin-bottom: 0.7rem;
}

.char-counter {
  text-align: right;
  color: var(--muted) !important;
  font-size: 0.8rem;
  font-family: 'JetBrains Mono', monospace;
  margin-top: -0.6rem;
  margin-bottom: 0.6rem;
}

.success-banner {
  background: #E8F7F0;
  color: #0F6B47 !important;
  border-left: 5px solid var(--success);
  border-radius: 10px;
  padding: 0.8rem 1.1rem;
  font-weight: 600;
  margin-bottom: 0.8rem;
}

.stButton > button {
  border-radius: 10px !important;
  font-weight: 600 !important;
  border: 1.5px solid var(--border) !important;
}
.stButton > button[kind="primary"] {
  background-color: var(--accent) !important;
  color: var(--accent-ink) !important;
  border: none !important;
}
.stButton > button[kind="primary"]:hover { filter: brightness(1.08); }

/* ปุ่มรอง (secondary) ต้องกำหนดพื้นหลัง+สีตัวอักษรเองด้วย ไม่งั้นจะพึ่งสีจาก
   ธีมของ Streamlit ซึ่งอาจกลายเป็นตัวหนังสือสีเข้ม (จากกฎด้านล่าง) บนพื้นหลัง
   เข้มของปุ่ม (จากธีม) แล้วมองไม่เห็นข้อความในปุ่มอีกแบบหนึ่ง */
.stButton > button:not([kind="primary"]),
.stDownloadButton > button {
  background-color: var(--card) !important;
  color: var(--ink) !important;
}

/* กล่องข้อความ native ของ Streamlit ที่ไม่ได้อยู่ใน div ของเราเอง (label ของ
   widget, st.caption, กล่อง info/warning/error, หัวข้อ expander, ชื่อแท็บ)
   เดิมพึ่งสีจากธีมของ Streamlit เอง ซึ่งบางครั้งเป็นสีขาว — บังคับให้เป็นสีเข้ม
   ของเราเสมอ ยืนยัน testid จากไฟล์ static ของ Streamlit เวอร์ชันนี้จริงๆ แล้ว */
[data-testid="stWidgetLabel"],
[data-testid="stWidgetLabel"] *,
[data-testid="stCaptionContainer"],
[data-testid="stCaptionContainer"] *,
[data-testid="stMarkdownContainer"],
[data-testid="stMarkdownContainer"] p,
[data-testid="stAlertContainer"],
[data-testid="stAlertContent"],
[data-testid="stAlertContainer"] *,
[data-testid="stExpander"] summary,
[data-testid="stExpander"] summary *,
[data-testid="stExpander"] p,
[data-testid="stTab"],
[data-testid="stTab"] *,
[data-testid="stTabs"] [data-baseweb="tab"],
[data-testid="stTabs"] [data-baseweb="tab"] * {
  color: var(--ink) !important;
}

/* แท็บที่กำลังถูกเลือกอยู่ ให้เน้นด้วยสี accent แทน เพื่อยังเห็นความต่างจากแท็บอื่น */
[data-testid="stTab"][aria-selected="true"],
[data-testid="stTab"][aria-selected="true"] * {
  color: #8A5A00 !important;
}

[data-testid="stTabs"] [data-baseweb="tab"] {
  font-family: 'Space Grotesk', sans-serif;
  font-weight: 600;
}

[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea {
  border-radius: 10px !important;
}
"""

st.markdown(f"<style>{CUSTOM_CSS}</style>", unsafe_allow_html=True)


# ============================================================
# 3) ข้อความสองภาษา TH / EN (I18N)
# ============================================================
# เพิ่ม/แก้ข้อความของ UI ได้ที่นี่ที่เดียว ทั้งสองภาษาต้องมี key ตรงกัน

TXT = {
    "TH": {
        "app_title": "⚡ Text Extractor",
        "banner": "แปลงข้อความยุ่งเหยิง ให้กลายเป็นโครงสร้างข้อมูลที่ก๊อปปี้ไปวางแอปไหนก็ฟอร์แมตไม่พัง",
        "hero_pain": "เบื่อไหม? Copy ข้อมูลจากไหนก็ไม่รู้ พอวางใน Notion แล้ว column เพี้ยน ต้องมานั่งไล่แก้ทีละบรรทัด",
        "sub_banner": "ฟอร์แมตเป๊ะ สำหรับสายจดโน้ต (Notion / Obsidian), สายสเปรดชีต (Excel / Google Sheets) และสายทำระบบ Automation (Make / Zapier)",
        "api_key_label": "🔑 Anthropic API Key",
        "api_key_placeholder": "sk-ant-...",
        "check_button": "🔑 Check",
        "go_pro_button": "👑 Go Pro",
        "go_pro_toast": "เลื่อนลงไปด้านล่างสุดของหน้าเพื่อปลดล็อก Pro ⬇️",
        "api_key_empty": "กรุณาใส่ API Key ก่อนตรวจสอบ",
        "api_key_valid": "API Key ใช้งานได้",
        "api_key_invalid": "API Key ไม่ถูกต้องหรือหมดอายุ",
        "api_key_error": "ตรวจสอบไม่สำเร็จ",
        "api_key_tutorial_note": "💡 ยังไม่มี API Key? คู่มือขอ Key จะเพิ่มเข้ามาเร็วๆ นี้",
        "step1_title": "STEP 1 · เลือกโครงสร้างข้อมูลที่ต้องการสกัด",
        "preset_label": "เลือกรูปแบบ (Preset)",
        "preset_placeholder": "👇 เลือกรูปแบบที่ต้องการ (Preset)",
        "preset_placeholder_hint": "กรุณาเลือกรูปแบบข้อมูลด้านบนก่อนเริ่มใช้งาน",
        "preset_custom_label": "✨ [PRO] Custom Schema Builder",
        "locked_fields_title": "🔒 ฟิลด์ที่จะสกัด (ค่าเริ่มต้น)",
        "upsell_text": "ต้องการฟิลด์เพิ่มหรือกำหนดชื่อฟิลด์เอง? ปลดล็อก Pro ได้ที่ด้านล่างสุดของหน้า ⬇️",
        "pro_builder_title": "✨ PRO · Custom Schema Builder",
        "pro_locked_title": "🔒 Preset นี้เป็นฟีเจอร์ Pro",
        "pro_locked_desc": "ปลดล็อกเพื่อกำหนดฟิลด์เองได้ไม่จำกัดจำนวน — เลื่อนลงไปที่ด้านล่างสุดของหน้าเพื่อใส่ License Key",
        "field_name_placeholder": "ชื่อฟิลด์ เช่น Customer_Location",
        "add_field_button": "➕ เพิ่มฟิลด์ใหม่",
        "remove_field_button": "ลบ",
        "step2_title": "STEP 2 · วางข้อความและสั่งประมวลผล",
        "text_area_label": "ข้อความดิบ",
        "text_area_placeholder": "วางข้อความที่ต้องการสกัดข้อมูล เช่น บันทึกการประชุม, รีวิวสินค้า, บทสนทนา ฯลฯ",
        "char_counter": "ตัวอักษร",
        "sample_button": "🎲 ลองใช้ข้อความตัวอย่าง",
        "convert_button": "⚡ Convert to Structured Data",
        "converting_status": "🔎 กำลังวิเคราะห์และตรวจสอบโครงสร้าง JSON...",
        "need_api_key_warning": "กรุณาใส่ Anthropic API Key ที่ด้านบนก่อนใช้งาน",
        "need_text_warning": "กรุณาใส่ข้อความก่อนกด Convert",
        "need_fields_warning": "กรุณากำหนดอย่างน้อย 1 ฟิลด์ก่อนกด Convert",
        "char_limit_warning": "ข้อความยาวเกินลิมิตของแผนฟรี ({limit} ตัวอักษร) — ปลดล็อก Pro เพื่อไม่จำกัดความยาว",
        "json_parse_error": "AI ตอบกลับมาไม่ใช่ JSON ที่ถูกต้อง ลองกดอีกครั้ง หรือดูข้อความดิบด้านล่าง",
        "rate_limit_error": "ถูกจำกัดอัตราการเรียกใช้ (Rate Limit) กรุณารอสักครู่แล้วลองใหม่",
        "generic_error": "เกิดข้อผิดพลาดระหว่างเรียก AI",
        "show_raw_response": "ดูข้อความดิบที่ AI ตอบกลับมา",
        "success_banner": "✅ สกัดข้อมูลสำเร็จภายใน {seconds} วินาที",
        "mock_note": "ตัวอย่างจำลอง ไม่ได้เรียก AI จริง",
        "copy_table_expander": "📋 คัดลอกตาราง (Copy Table)",
        "copy_button_table": "📋 คัดลอกตาราง",
        "copy_button_json": "📋 คัดลอก JSON",
        "copy_button_markdown": "📋 คัดลอก Markdown",
        "helper_copy_table_md": "พร้อมนำไป Paste ลงใน Notion Database หรือ Google Sheets ได้ทันที โดยตารางไม่เบี้ยว",
        "helper_copy_markdown_obsidian": "พร้อมนำไป Paste ลงใน Obsidian ได้ทันที โดย syntax markdown ไม่เพี้ยน",
        "helper_download_csv": "พร้อมนำไป Import เข้า Excel / Google Sheets ได้แบบฟอร์แมตไม่พัง",
        "helper_copy_json": "ผ่านการตรวจสอบ Syntax 100% พร้อมนำไปใช้ใน Webhook/Automation Pipeline",
        "tab_table": "📊 Interactive Table",
        "tab_json": "💻 Raw JSON",
        "tab_export": "📥 Export Options",
        "download_csv": "⬇️ Download CSV",
        "webhook_pro_locked": "🔒 การส่งออกไปยัง Webhook / Make.com / Zapier เป็นฟีเจอร์ Pro",
        "webhook_url_label": "Webhook URL",
        "webhook_send_button": "🚀 ส่งไปยัง Webhook",
        "webhook_url_missing": "กรุณาใส่ Webhook URL ก่อน",
        "webhook_sent_success": "ส่งข้อมูลไปยัง Webhook สำเร็จ",
        "webhook_sent_failed": "ส่งข้อมูลไม่สำเร็จ",
        "conversion_title": "🔓 ต้องการฟิลด์กำหนดเอง? ปลดล็อก Pro Custom Schema Builder",
        "license_key_label": "Pro License Key",
        "license_key_placeholder": "วาง License Key ที่ได้รับทางอีเมลจาก Gumroad",
        "activate_button": "🔓 Activate Pro",
        "pro_active_badge": "👑 บัญชีนี้เป็น Pro แล้ว ใช้งานได้ไม่จำกัด",
        "license_not_configured": "ยังไม่ได้ตั้งค่า GUMROAD_PRODUCT_ID บน Space นี้ (สำหรับผู้พัฒนา)",
        "license_empty": "กรุณาใส่ License Key ก่อนกด Activate",
        "license_valid": "ปลดล็อก Pro สำเร็จ",
        "license_invalid": "License Key ไม่ถูกต้อง",
        "license_error": "ตรวจสอบ License Key ไม่สำเร็จ",
    },
    "EN": {
        "app_title": "⚡ Text Extractor",
        "banner": "Transform messy text into structured data that never breaks when pasted into any app.",
        "hero_pain": "Tired of pasting data somewhere only to watch the formatting fall apart?",
        "sub_banner": "Perfect formatting built for note-takers (Notion / Obsidian), spreadsheet users (Excel / Google Sheets), and automation workflows (Make / Zapier).",
        "api_key_label": "🔑 Anthropic API Key",
        "api_key_placeholder": "sk-ant-...",
        "check_button": "🔑 Check",
        "go_pro_button": "👑 Go Pro",
        "go_pro_toast": "Scroll to the bottom of the page to unlock Pro ⬇️",
        "api_key_empty": "Please enter an API key before checking",
        "api_key_valid": "API key is valid",
        "api_key_invalid": "API key is invalid or expired",
        "api_key_error": "Could not verify key",
        "api_key_tutorial_note": "💡 Don't have a key yet? A how-to guide is coming soon",
        "step1_title": "STEP 1 · Choose the data structure to extract",
        "preset_label": "Choose a preset",
        "preset_placeholder": "👇 Choose the preset you'd like to use",
        "preset_placeholder_hint": "Please choose a data format above to get started",
        "preset_custom_label": "✨ [PRO] Custom Schema Builder",
        "locked_fields_title": "🔒 Fields to extract (fixed)",
        "upsell_text": "Need more fields or custom names? Unlock Pro at the bottom of the page ⬇️",
        "pro_builder_title": "✨ PRO · Custom Schema Builder",
        "pro_locked_title": "🔒 This preset is a Pro feature",
        "pro_locked_desc": "Unlock unlimited custom fields — scroll to the bottom of the page to enter your license key",
        "field_name_placeholder": "Field name, e.g. Customer_Location",
        "add_field_button": "➕ Add field",
        "remove_field_button": "Remove",
        "step2_title": "STEP 2 · Paste your text and run it",
        "text_area_label": "Raw text",
        "text_area_placeholder": "Paste the text you want to extract data from — meeting notes, reviews, transcripts, etc.",
        "char_counter": "characters",
        "sample_button": "🎲 Try sample text",
        "convert_button": "⚡ Convert to Structured Data",
        "converting_status": "🔎 Analyzing and validating JSON structure...",
        "need_api_key_warning": "Please enter your Anthropic API key above first",
        "need_text_warning": "Please enter some text before converting",
        "need_fields_warning": "Please define at least 1 field before converting",
        "char_limit_warning": "Text exceeds the free plan limit ({limit} characters) — unlock Pro for unlimited length",
        "json_parse_error": "The AI's response wasn't valid JSON. Try again, or check the raw response below",
        "rate_limit_error": "Rate limited — please wait a moment and try again",
        "generic_error": "Something went wrong calling the AI",
        "show_raw_response": "View the AI's raw response",
        "success_banner": "✅ Data extracted successfully in {seconds}s",
        "mock_note": "sample preview, no real AI call made",
        "copy_table_expander": "📋 Copy Table",
        "copy_button_table": "📋 Copy Table",
        "copy_button_json": "📋 Copy JSON",
        "copy_button_markdown": "📋 Copy Markdown",
        "helper_copy_table_md": "Ready to paste straight into your Notion database or Google Sheets — the table stays perfectly intact.",
        "helper_copy_markdown_obsidian": "Ready to paste straight into Obsidian — the markdown syntax stays intact.",
        "helper_download_csv": "Ready to import into Excel / Google Sheets with formatting fully intact.",
        "helper_copy_json": "100% syntax-validated — ready to drop into your Webhook / Automation pipeline.",
        "tab_table": "📊 Interactive Table",
        "tab_json": "💻 Raw JSON",
        "tab_export": "📥 Export Options",
        "download_csv": "⬇️ Download CSV",
        "webhook_pro_locked": "🔒 Exporting to Webhook / Make.com / Zapier is a Pro feature",
        "webhook_url_label": "Webhook URL",
        "webhook_send_button": "🚀 Send to Webhook",
        "webhook_url_missing": "Please enter a Webhook URL first",
        "webhook_sent_success": "Sent to your webhook successfully",
        "webhook_sent_failed": "Failed to send",
        "conversion_title": "🔓 Need custom fields? Unlock the Pro Custom Schema Builder",
        "license_key_label": "Pro License Key",
        "license_key_placeholder": "Paste the license key you received by email from Gumroad",
        "activate_button": "🔓 Activate Pro",
        "pro_active_badge": "👑 This session is Pro — unlimited usage",
        "license_not_configured": "GUMROAD_PRODUCT_ID isn't set on this Space yet (developer note)",
        "license_empty": "Please enter a license key before activating",
        "license_valid": "Pro unlocked successfully",
        "license_invalid": "Invalid license key",
        "license_error": "Could not verify the license key",
    },
}


# ============================================================
# 4) ค่าคงที่ของระบบ (CONSTANTS)
# ============================================================

# โมเดล Claude ที่ใช้สกัดข้อมูล — Haiku เร็วและถูก เหมาะกับงาน extraction
# ถ้าต้องการความแม่นยำสูงขึ้นสำหรับ schema ที่ซับซ้อน เปลี่ยนเป็น "claude-sonnet-4-6" ได้
DEFAULT_MODEL = "claude-haiku-4-5"

FREE_CHAR_LIMIT = 1500
PRO_CHAR_LIMIT = 20000

# ตั้งค่านี้ผ่าน Repository secrets บน Hugging Face Space (ไม่ต้องแก้ในโค้ด)
GUMROAD_PRODUCT_ID = os.environ.get("GUMROAD_PRODUCT_ID", "")


# ============================================================
# 5) ข้อมูล PRESET ทั้ง 4 แบบ (ฟรี) + ตัวอย่างข้อความ/ผลลัพธ์จำลอง
# ============================================================

PRESETS = {
    "meeting_notes": {
        "label_th": "📝 สรุปการประชุม (Meeting Notes)",
        "label_en": "📝 Meeting Notes",
        "fields": [
            {"name": "Summary", "desc_th": "สรุปสาระสำคัญของการประชุม ไม่เกิน 3 บรรทัด",
             "desc_en": "Concise summary of the meeting, max 3 lines"},
            {"name": "Action_Items", "desc_th": "รายการงานที่ต้องทำต่อ พร้อมผู้รับผิดชอบ",
             "desc_en": "Action items to follow up on, with the owner responsible"},
            {"name": "Key_Decisions", "desc_th": "มติที่ประชุมและข้อสรุปการตัดสินใจ",
             "desc_en": "Key decisions and conclusions reached in the meeting"},
        ],
        "sample_text_th": (
            "ที่ประชุมทีมการตลาดวันนี้สรุปว่ายอดขายไตรมาสนี้เพิ่มขึ้น 15% จากแคมเปญโซเชียลมีเดีย "
            "ทีมตกลงว่าจะเพิ่มงบโฆษณา Facebook อีก 20% ในเดือนหน้า และมอบหมายให้คุณสมชายจัดทำ"
            "รายงานสรุปผลแคมเปญภายในวันศุกร์ ส่วนคุณสมหญิงรับผิดชอบติดต่อ Influencer รายใหม่ 3 ราย "
            "ที่ประชุมยังตัดสินใจเลื่อนการเปิดตัวสินค้าใหม่จากสัปดาห์หน้าไปเป็นต้นเดือนหน้าเพื่อให้ทีมเตรียมตัวได้ทันเวลา"
        ),
        "sample_text_en": (
            "Today's marketing team meeting confirmed that quarterly sales grew 15% thanks to the "
            "social media campaign. The team agreed to increase the Facebook ad budget by 20% next "
            "month, and assigned Alex to prepare a campaign summary report by Friday. Jordan will "
            "reach out to 3 new influencers. The meeting also decided to postpone the new product "
            "launch from next week to early next month to give the team more time to prepare."
        ),
        "sample_output_th": [{
            "Summary": "ยอดขายไตรมาสนี้เพิ่มขึ้น 15% จากแคมเปญโซเชียลมีเดีย ทีมตกลงเพิ่มงบโฆษณาและเลื่อนวันเปิดตัวสินค้าใหม่",
            "Action_Items": "สมชาย: จัดทำรายงานสรุปแคมเปญภายในวันศุกร์ | สมหญิง: ติดต่อ Influencer รายใหม่ 3 ราย",
            "Key_Decisions": "เพิ่มงบโฆษณา Facebook 20% ในเดือนหน้า และเลื่อนเปิดตัวสินค้าใหม่ไปต้นเดือนหน้า",
        }],
        "sample_output_en": [{
            "Summary": "Quarterly sales grew 15% thanks to the social campaign. The team agreed to raise ad spend and delay the launch.",
            "Action_Items": "Alex: prepare campaign summary report by Friday | Jordan: contact 3 new influencers",
            "Key_Decisions": "Increase Facebook ad budget by 20% next month; postpone product launch to early next month",
        }],
    },
    "product_reviews": {
        "label_th": "⭐ รีวิวสินค้า (Product Reviews)",
        "label_en": "⭐ Product Reviews",
        "fields": [
            {"name": "Rating_Score", "desc_th": "คะแนนรีวิวสินค้า ระบุเป็นสเกล 1 ถึง 5",
             "desc_en": "Product rating, expressed on a 1–5 scale"},
            {"name": "Sentiment", "desc_th": "วิเคราะห์ความรู้สึก (Positive / Neutral / Negative)",
             "desc_en": "Sentiment analysis (Positive / Neutral / Negative)"},
            {"name": "Main_Feedback", "desc_th": "สรุปข้อดี ข้อเสีย หรือจุดติดใจ ไม่เกิน 3 บรรทัด",
             "desc_en": "Summary of pros, cons, or key concerns, max 3 lines"},
        ],
        "sample_text_th": (
            "รีวิวที่ 1: หูฟังตัวนี้เสียงดีมากเบสหนักแน่น ใส่สบายไม่ปวดหู แต่แบตอึดแค่ 4 ชั่วโมง"
            "ทำให้ต้องชาร์จบ่อย ให้ 4 ดาวครับ\n\n"
            "รีวิวที่ 2: ผิดหวังมาก สั่งมาสีดำแต่ได้สีขาว แถมกล่องยับด้วย ติดต่อร้านก็เงียบ ไม่แนะนำเลย 1 ดาว"
        ),
        "sample_text_en": (
            "Review 1: These headphones sound amazing, deep punchy bass and super comfortable for "
            "long sessions. Battery only lasts 4 hours though, so I have to charge often. 4 stars.\n\n"
            "Review 2: Very disappointed. I ordered black but received white, and the box arrived "
            "crushed. The seller hasn't replied to my messages. Not recommended. 1 star."
        ),
        "sample_output_th": [
            {"Rating_Score": "4/5", "Sentiment": "Positive", "Main_Feedback": "เสียงดี เบสหนักแน่น ใส่สบาย แต่แบตอยู่ได้แค่ 4 ชั่วโมง"},
            {"Rating_Score": "1/5", "Sentiment": "Negative", "Main_Feedback": "ได้สินค้าผิดสี กล่องเสียหาย และร้านไม่ตอบกลับ"},
        ],
        "sample_output_en": [
            {"Rating_Score": "4/5", "Sentiment": "Positive", "Main_Feedback": "Great sound and comfort, but battery life is short at 4 hours"},
            {"Rating_Score": "1/5", "Sentiment": "Negative", "Main_Feedback": "Wrong color shipped, damaged box, and no response from seller"},
        ],
    },
    "video_script": {
        "label_th": "🎬 บทวิดีโอ/พอดแคสต์ (Video Script / Podcast)",
        "label_en": "🎬 Video Script / Podcast",
        "fields": [
            {"name": "Core_Topic", "desc_th": "หัวข้อหลักที่พูดถึง", "desc_en": "Main topic being discussed"},
            {"name": "Key_Quotes", "desc_th": "ประโยคเด็ดหรือคำพูดที่น่าสนใจ", "desc_en": "Standout quote or memorable line"},
            {"name": "Target_Audience", "desc_th": "กลุ่มเป้าหมายที่เหมาะกับเนื้อหานี้", "desc_en": "Target audience this content is best suited for"},
        ],
        "sample_text_th": (
            "ในตอนนี้เราจะมาคุยกันเรื่องการบริหารเวลาสำหรับฟรีแลนซ์ หลายคนบ่นว่าทำงานที่บ้านแล้วไม่มีขอบเขตเวลา "
            "วันนี้แขกรับเชิญของเราบอกว่า 'ถ้าคุณไม่กำหนดเวลาเลิกงานให้ตัวเอง งานจะกินเวลาชีวิตคุณทั้งหมด' "
            "เธอแนะนำให้ใช้เทคนิค Time Blocking และปิดแจ้งเตือนหลัง 6 โมงเย็น พอดแคสต์ตอนนี้เหมาะกับฟรีแลนซ์"
            "และคนทำงานสายครีเอทีฟที่กำลังเริ่มต้นบริหารเวลาตัวเอง"
        ),
        "sample_text_en": (
            "In this episode we're talking about time management for freelancers. So many people say "
            "working from home means there's no real boundary on their day. Our guest today put it "
            "perfectly: 'If you don't set a hard stop for yourself, work will eat your entire life.' "
            "She recommends time blocking and turning off notifications after 6pm. This episode is "
            "for freelancers and creatives who are just starting to take control of their schedule."
        ),
        "sample_output_th": [{
            "Core_Topic": "การบริหารเวลาสำหรับฟรีแลนซ์ โดยเน้นการตั้งขอบเขตเวลาทำงาน",
            "Key_Quotes": "ถ้าคุณไม่กำหนดเวลาเลิกงานให้ตัวเอง งานจะกินเวลาชีวิตคุณทั้งหมด",
            "Target_Audience": "ฟรีแลนซ์และคนทำงานสายครีเอทีฟที่เพิ่งเริ่มบริหารเวลาตัวเอง",
        }],
        "sample_output_en": [{
            "Core_Topic": "Time management for freelancers, focused on setting work boundaries",
            "Key_Quotes": "If you don't set a hard stop for yourself, work will eat your entire life.",
            "Target_Audience": "Freelancers and creative professionals new to managing their own schedule",
        }],
    },
    "raw_text_table": {
        "label_th": "📋 แปลงข้อความทั่วไปเป็นตาราง (Raw Text to Table)",
        "label_en": "📋 Raw Text to Table",
        "fields": [
            {"name": "Main_Entity", "desc_th": "ชื่อสิ่งของ/บุคคล/องค์กรหลักที่กล่าวถึง",
             "desc_en": "Name of the main item, person, or organization mentioned"},
            {"name": "Attribute", "desc_th": "คุณลักษณะ คุณสมบัติ หรือรายละเอียดที่เกี่ยวข้อง",
             "desc_en": "Key attribute, property, or relevant detail"},
            {"name": "Category", "desc_th": "การจัดหมวดหมู่หรือประเภทของข้อมูล",
             "desc_en": "Category or classification of the item"},
        ],
        "sample_text_th": (
            "ร้านเรามีสินค้าขายดี 3 อย่าง คือ กาแฟดริปเมล็ดเดี่ยวเอธิโอเปีย ราคา 180 บาท "
            "เป็นสินค้าประเภทเครื่องดื่ม, โน้ตบุ๊คสำหรับจดบันทึกปกหนังแท้ ราคา 450 บาท ประเภทเครื่องเขียน "
            "และเทียนหอมกลิ่นลาเวนเดอร์ ราคา 320 บาท ประเภทของแต่งบ้าน"
        ),
        "sample_text_en": (
            "Our shop's 3 best sellers are: single-origin Ethiopian drip coffee at 180 baht, a "
            "beverage item; a genuine leather notebook at 450 baht, a stationery item; and a "
            "lavender-scented candle at 320 baht, a home decor item."
        ),
        "sample_output_th": [
            {"Main_Entity": "กาแฟดริปเมล็ดเดี่ยวเอธิโอเปีย", "Attribute": "ราคา 180 บาท", "Category": "เครื่องดื่ม"},
            {"Main_Entity": "โน้ตบุ๊คปกหนังแท้", "Attribute": "ราคา 450 บาท", "Category": "เครื่องเขียน"},
            {"Main_Entity": "เทียนหอมกลิ่นลาเวนเดอร์", "Attribute": "ราคา 320 บาท", "Category": "ของแต่งบ้าน"},
        ],
        "sample_output_en": [
            {"Main_Entity": "Single-origin Ethiopian drip coffee", "Attribute": "180 baht", "Category": "Beverage"},
            {"Main_Entity": "Genuine leather notebook", "Attribute": "450 baht", "Category": "Stationery"},
            {"Main_Entity": "Lavender-scented candle", "Attribute": "320 baht", "Category": "Home decor"},
        ],
    },
}


# ============================================================
# 6) ตั้งค่า SESSION STATE เริ่มต้น
# ============================================================
# ทุกตัวแปรที่ผูกกับ widget (key=...) ต้องถูกกำหนดค่าเริ่มต้นไว้ที่นี่ก่อนเสมอ

_DEFAULTS = {
    "lang": "TH",
    "api_key_input": "",
    "api_key_status": None,       # None | "valid" | "invalid"
    "api_key_message": "",
    "is_pro": True,
    "preset_choice": None,
    "custom_field_ids": [0, 1, 2],
    "next_field_id": 3,
    "raw_text_input": "",
    "last_records": None,
    "last_fields": None,
    "last_raw_response": "",
    "last_elapsed": None,
    "last_error": None,
    "last_is_mock": False,
    "license_key_input": "",
    "license_message": "",
    "webhook_url_input": "",
   
}
for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v
if "app_api_key" not in st.session_state:
    st.session_state.app_api_key = None
with st.expander("📖 วิธีขอ Anthropic API Key (คลิกเพื่อดู)"):
    st.markdown("""
    1. เข้าไปที่เว็บ [console.anthropic.com](https://console.anthropic.com/)
    2. สมัครสมาชิก หรือ Log in เข้าสู่ระบบ
    3. ไปที่เมนู **API Keys** แล้วกด **Create Key**
    4. คัดลอกรหัสที่ขึ้นต้นด้วย `sk-ant-...` นำมาวางในช่องกรอกด้านบนได้เลยครับ
    """)
# ============================================================
# 7) ฟังก์ชันช่วยเหลือ (HELPERS)
# ============================================================

def t(key):
    """ดึงข้อความตามภาษาปัจจุบัน (TH/EN)"""
    return TXT[st.session_state.lang].get(key, key)


def get_active_fields():
    """คืนรายการฟิลด์ที่ต้องสกัด ตาม preset ที่เลือกอยู่ตอนนี้"""
    choice = st.session_state.preset_choice
    if choice == "custom":
        names = []
        for fid in st.session_state.custom_field_ids:
            val = st.session_state.get(f"cf_{fid}", "").strip()
            if val:
                names.append(val)
        return [{"name": n, "desc_th": f"ค่าของฟิลด์ {n}", "desc_en": f"the value for {n}"} for n in names]
    preset = PRESETS.get(choice)
    return preset["fields"] if preset else []


def make_preset_formatter(lang, is_pro):
    """คืนฟังก์ชัน format_func สำหรับ selectbox โดย 'จำ' ค่า lang/is_pro ไว้ตรงๆ
    (ไม่ไปอ่าน st.session_state ซ้ำตอนถูกเรียกทีหลัง) เพื่อให้ผลลัพธ์เสถียร
    ไม่ว่า Streamlit จะเรียกฟังก์ชันนี้ซ้ำตอนไหนก็ตาม"""
    def _format(key):
        if key is None:
            return TXT[lang]["preset_placeholder"]
        if key == "custom":
            base = TXT[lang]["preset_custom_label"]
            return base if is_pro else base + " 🔒"
        return PRESETS[key]["label_th" if lang == "TH" else "label_en"]
    return _format


def on_preset_change():
    st.session_state.last_records = None
    st.session_state.last_error = None
    st.session_state.last_is_mock = False


def add_custom_field():
    new_id = st.session_state.next_field_id
    st.session_state.custom_field_ids.append(new_id)
    st.session_state.next_field_id += 1
    st.session_state[f"cf_{new_id}"] = ""


def remove_custom_field(field_id):
    if field_id in st.session_state.custom_field_ids:
        st.session_state.custom_field_ids.remove(field_id)


def use_sample_text():
    """ใส่ข้อความตัวอย่าง + โชว์ผลลัพธ์จำลองทันที ไม่เรียก AI จริง (ประหยัด API cost)"""
    preset = PRESETS.get(st.session_state.preset_choice)
    if not preset:
        return
    lang_suffix = "th" if st.session_state.lang == "TH" else "en"
    st.session_state.raw_text_input = preset[f"sample_text_{lang_suffix}"]
    st.session_state.last_records = preset[f"sample_output_{lang_suffix}"]
    st.session_state.last_fields = preset["fields"]
    st.session_state.last_elapsed = 0.0
    st.session_state.last_error = None
    st.session_state.last_is_mock = True


def check_api_key(api_key):
    """ยิง request เบาๆ (models.retrieve) ไปเช็คว่า key ใช้งานได้ไหม ไม่เสีย token"""
    if not api_key or not api_key.strip():
        return False, t("api_key_empty")
    try:
        client = anthropic.Anthropic(api_key=api_key.strip())
        client.models.retrieve(DEFAULT_MODEL)
        return True, t("api_key_valid")
    except anthropic.AuthenticationError:
        return False, t("api_key_invalid")
    except Exception as e:
        return False, f"{t('api_key_error')}: {e}"


def build_extraction_prompt(fields, raw_text, lang):
    lines = []
    for f in fields:
        desc = f.get("desc_th" if lang == "TH" else "desc_en") or f"the value for {f['name']}"
        lines.append(f'- "{f["name"]}": {desc}')
    field_block = "\n".join(lines)
    field_names = [f["name"] for f in fields]
    return f"""You are a precise data-extraction engine. Read the raw text below and extract the requested fields.

Rules:
- Return ONLY a valid JSON array of objects. No markdown formatting, no code fences, no explanation before or after.
- Each object must contain exactly these keys: {field_names}
- If the raw text clearly describes multiple distinct items/records, return one object per item.
- If it describes only one item, return an array containing exactly one object.
- If a field's value cannot be found in the text, use an empty string "" for that field. Never invent facts that are not in the text.
- Keep field values concise and in the same language as the raw text.

Fields to extract:
{field_block}

Raw text:
\"\"\"
{raw_text}
\"\"\"

Respond with the JSON array only."""


def call_claude_extract(api_key, fields, raw_text, lang):
    client = anthropic.Anthropic(api_key=api_key)
    prompt = build_extraction_prompt(fields, raw_text, lang)
    start = time.time()
    message = client.messages.create(
        model=DEFAULT_MODEL,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    elapsed = time.time() - start
    raw_output = "".join(
        block.text for block in message.content if getattr(block, "type", "") == "text"
    )
    return raw_output, elapsed


def parse_json_array(raw_output):
    cleaned = raw_output.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    data = json.loads(cleaned.strip())
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        raise ValueError("Expected a JSON array")
    return data


def do_convert():
    st.session_state.last_error = None
    st.session_state.last_is_mock = False

    api_key = st.session_state.api_key_input.strip()
    raw_text = st.session_state.raw_text_input.strip()
    fields = get_active_fields()
    char_limit = PRO_CHAR_LIMIT if st.session_state.is_pro else FREE_CHAR_LIMIT

    if not api_key:
        st.session_state.last_error = t("need_api_key_warning")
        return
    if not raw_text:
        st.session_state.last_error = t("need_text_warning")
        return
    if not fields:
        st.session_state.last_error = t("need_fields_warning")
        return
    if len(raw_text) > char_limit:
        st.session_state.last_error = t("char_limit_warning").format(limit=char_limit)
        return

    try:
        raw_output, elapsed = call_claude_extract(api_key, fields, raw_text, st.session_state.lang)
    except anthropic.AuthenticationError:
        st.session_state.last_error = t("api_key_invalid")
        return
    except anthropic.RateLimitError:
        st.session_state.last_error = t("rate_limit_error")
        return
    except Exception as e:
        st.session_state.last_error = f"{t('generic_error')}: {e}"
        return

    try:
        records = parse_json_array(raw_output)
    except Exception:
        st.session_state.last_error = t("json_parse_error")
        st.session_state.last_raw_response = raw_output
        return

    st.session_state.last_records = records
    st.session_state.last_fields = fields
    st.session_state.last_raw_response = raw_output
    st.session_state.last_elapsed = elapsed


def verify_gumroad_license(license_key):
    if not GUMROAD_PRODUCT_ID:
        return False, t("license_not_configured")
    if not license_key or not license_key.strip():
        return False, t("license_empty")
    try:
        resp = requests.post(
            "https://api.gumroad.com/v2/licenses/verify",
            data={
                "product_id": GUMROAD_PRODUCT_ID,
                "license_key": license_key.strip(),
                "increment_uses_count": "false",
            },
            timeout=10,
        )
        data = resp.json()
        if data.get("success"):
            return True, t("license_valid")
        return False, data.get("message", t("license_invalid"))
    except requests.RequestException as e:
        return False, f"{t('license_error')}: {e}"


def records_to_markdown(records, fields):
    if not records:
        return ""
    names = [f["name"] for f in fields] if fields else list(records[0].keys())
    header = "| " + " | ".join(names) + " |"
    sep = "| " + " | ".join(["---"] * len(names)) + " |"
    rows = []
    for r in records:
        row = "| " + " | ".join(str(r.get(n, "")).replace("\n", " ") for n in names) + " |"
        rows.append(row)
    return "\n".join([header, sep] + rows)


def records_to_html_table(records, fields):
    """สร้างตาราง HTML จริง (<table><tr><td>) แทน text ล้วน เพราะ Notion/Google
    Sheets ต้องเจอ HTML table ถึงจะแยกช่องแถว-คอลัมน์ให้ตอน paste — แค่ text
    คั่นด้วย tab (TSV) นั้น Google Sheets อ่านออกแต่ Notion อ่านไม่ออก

    ใส่ <thead>/<tbody> ครบและมี inline border ไว้ด้วย เผื่อตัว parser ของ
    แอปปลายทางใช้โครงสร้าง/สไตล์เป็นสัญญาณว่า 'นี่คือตารางจริง' ไม่ใช่แค่
    ข้อความที่บังเอิญมีแท็ก table"""
    if not records:
        return ""
    names = [f["name"] for f in fields] if fields else list(records[0].keys())
    cell_style = "border:1px solid #999;padding:4px 8px;"
    thead = (
        "<thead><tr>"
        + "".join(f'<th style="{cell_style}">{html.escape(str(n))}</th>' for n in names)
        + "</tr></thead>"
    )
    body_rows = []
    for r in records:
        cells = "".join(
            f'<td style="{cell_style}">{html.escape(str(r.get(n, "")))}</td>' for n in names
        )
        body_rows.append(f"<tr>{cells}</tr>")
    tbody = "<tbody>" + "".join(body_rows) + "</tbody>"
    return f'<table style="border-collapse:collapse;">{thead}{tbody}</table>'


def wrap_html_for_clipboard(table_html):
    """ห่อ HTML table ด้วย envelope แบบเดียวกับที่เบราว์เซอร์ใส่ให้อัตโนมัติ
    ตอนเรา copy ตารางจริงบนหน้าเว็บด้วยเมาส์ (มี <html><body> ครบ, มี meta
    charset, และ comment marker StartFragment/EndFragment บอกขอบเขต) — Notion
    ตรวจสอบรูปแบบนี้อย่างเข้มงวด ถ้าได้แค่ <table> เปล่าๆ จะไม่ยอมรับว่าเป็น
    ตาราง แล้ว fallback ไปวางเป็นก้อนข้อความก้อนเดียวแทน"""
    return (
        '<html><head><meta charset="utf-8"></head><body>'
        "<!--StartFragment-->" + table_html + "<!--EndFragment-->"
        "</body></html>"
    )


_COPY_BUTTON_TEMPLATE = """
<div style="margin: 0.3rem 0 0.8rem 0;">
  <textarea id="ta___KEY__" style="position:absolute; left:-9999px; top:-9999px;">__TEXT__</textarea>
  <button id="btn___KEY__" data-original="__LABEL__"
    style="background: var(--accent); color: var(--accent-ink); border: none;
           border-radius: 8px; padding: 0.5rem 1.1rem; font-weight: 600;
           cursor: pointer; font-family: 'Inter', sans-serif; font-size: 0.9rem;">__LABEL__</button>
</div>
<script>
(function() {
  var ta = document.getElementById('ta___KEY__');
  var btn = document.getElementById('btn___KEY__');
  if (!btn || btn.dataset.bound === '1') { return; }
  btn.dataset.bound = '1';
  btn.addEventListener('click', function() {
    function showCopied() {
      btn.innerText = '✅ Copied!';
      setTimeout(function() { btn.innerText = btn.getAttribute('data-original'); }, 1500);
    }
    function fallbackPlainCopy() {
      ta.style.position = 'fixed';
      ta.style.left = '0';
      ta.select();
      document.execCommand('copy');
      ta.style.position = 'absolute';
      ta.style.left = '-9999px';
      showCopied();
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(ta.value).then(showCopied).catch(fallbackPlainCopy);
    } else {
      fallbackPlainCopy();
    }
  });
})();
</script>
"""


def render_copy_button(text_to_copy, button_label, unique_key):
    """ปุ่มคัดลอกที่มองเห็นชัดเจนตลอดเวลา (ไม่ต้องเอาเมาส์ไปชี้ถึงจะโผล่)
    เพราะไอคอน copy ที่ติดมากับ st.code() อาจสังเกตเห็นยากสำหรับผู้ใช้บางคน

    สำคัญ: ใช้ st.html(unsafe_allow_javascript=True) ไม่ใช่ st.markdown() —
    เพราะ st.markdown(unsafe_allow_html=True) จะถูก sanitizer ของ Streamlit
    (DOMPurify) ตัด attribute onclick="..." ทิ้งอัตโนมัติเงียบๆ (ป้องกัน XSS)
    ทำให้ปุ่มโชว์ปกติแต่กดแล้วไม่ทำอะไรเลย — ต้องผูก event ผ่าน <script> +
    addEventListener แทน ซึ่งต้องมากับ st.html ที่เปิด unsafe_allow_javascript"""
    widget_html = (
        _COPY_BUTTON_TEMPLATE
        .replace("__TEXT__", html.escape(text_to_copy))
        .replace("__KEY__", unique_key)
        .replace("__LABEL__", button_label)
    )
    st.html(widget_html, unsafe_allow_javascript=True)


_COPY_TABLE_BUTTON_TEMPLATE = """
<div style="margin: 0.3rem 0 0.8rem 0;">
  <textarea id="tatext___KEY__" style="position:absolute; left:-9999px; top:-9999px;">__TEXT__</textarea>
  <textarea id="tahtml___KEY__" style="position:absolute; left:-9999px; top:-9999px;">__HTML__</textarea>
  <button id="btn___KEY__" data-original="__LABEL__"
    style="background: var(--accent); color: var(--accent-ink); border: none;
           border-radius: 8px; padding: 0.5rem 1.1rem; font-weight: 600;
           cursor: pointer; font-family: 'Inter', sans-serif; font-size: 0.9rem;">__LABEL__</button>
</div>
<script>
(function() {
  var taText = document.getElementById('tatext___KEY__');
  var taHtml = document.getElementById('tahtml___KEY__');
  var btn = document.getElementById('btn___KEY__');
  if (!btn || btn.dataset.bound === '1') { return; }
  btn.dataset.bound = '1';
  btn.addEventListener('click', function() {
    function showCopied() {
      btn.innerText = '✅ Copied!';
      setTimeout(function() { btn.innerText = btn.getAttribute('data-original'); }, 1500);
    }
    function fallbackPlainCopy() {
      taText.style.position = 'fixed';
      taText.style.left = '0';
      taText.select();
      document.execCommand('copy');
      taText.style.position = 'absolute';
      taText.style.left = '-9999px';
      showCopied();
    }
    if (navigator.clipboard && window.ClipboardItem) {
      try {
        var htmlBlob = new Blob([taHtml.value], { type: 'text/html' });
        var textBlob = new Blob([taText.value], { type: 'text/plain' });
        var item = new ClipboardItem({ 'text/html': htmlBlob, 'text/plain': textBlob });
        navigator.clipboard.write([item]).then(showCopied).catch(fallbackPlainCopy);
      } catch (e) {
        fallbackPlainCopy();
      }
    } else if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(taText.value).then(showCopied).catch(fallbackPlainCopy);
    } else {
      fallbackPlainCopy();
    }
  });
})();
</script>
"""


def render_dual_copy_button(html_content, plain_text, button_label, unique_key):
    """ปุ่มคัดลอกแบบ 'สองฟอร์แมตพร้อมกันในคลิกเดียว' — ใส่ทั้ง HTML และ
    plain text ลงคลิปบอร์ดพร้อมกัน แอปที่รับ HTML ได้ (Notion, Google Sheets)
    จะได้ตารางจริง ส่วนแอปที่รับได้แค่ข้อความล้วน (เช่น Obsidian ตอนใช้กับ
    markdown source) จะได้ plain_text ที่ส่งมาแทนโดยอัตโนมัติ ผู้ใช้ไม่ต้อง
    เลือกฟอร์แมตเอง — ผู้เรียกเป็นคนกำหนดว่า plain_text คืออะไร (TSV หรือ
    markdown syntax) ส่วน html_content ควรผ่าน wrap_html_for_clipboard() มาก่อน

    ใช้ st.html(unsafe_allow_javascript=True) ด้วยเหตุผลเดียวกับ render_copy_button
    ด้านบน — onclick attribute จะโดน sanitizer ตัดทิ้งถ้าใช้ st.markdown ธรรมดา"""
    widget_html = (
        _COPY_TABLE_BUTTON_TEMPLATE
        .replace("__TEXT__", html.escape(plain_text))
        .replace("__HTML__", html.escape(html_content))
        .replace("__KEY__", unique_key)
        .replace("__LABEL__", button_label)
    )
    st.html(widget_html, unsafe_allow_javascript=True)


def send_to_webhook():
    url = st.session_state.webhook_url_input.strip()
    if not url:
        st.warning(t("webhook_url_missing"))
        return
    try:
        resp = requests.post(url, json=st.session_state.last_records, timeout=10)
        if resp.ok:
            st.success(t("webhook_sent_success"))
        else:
            st.error(f"{t('webhook_sent_failed')} ({resp.status_code})")
    except requests.RequestException as e:
        st.error(f"{t('webhook_sent_failed')}: {e}")


def activate_pro():
    ok, msg = verify_gumroad_license(st.session_state.license_key_input)
    st.session_state.is_pro = ok
    st.session_state.license_message = msg
    st.session_state.app_api_key = None


# ============================================================
# 8) HEADER ZONE
# ============================================================

top_cols = st.columns([4.2, 1.3, 1.2])
with top_cols[0]:
    st.markdown(f'<div class="logo-title">{t("app_title")}</div>', unsafe_allow_html=True)
with top_cols[1]:
    st.radio("🌐 Language / ภาษา", ["TH", "EN"], horizontal=True, key="lang")
with top_cols[2]:
    st.markdown("<div style='height: 1.9rem;'></div>", unsafe_allow_html=True)
    if st.button(t("go_pro_button"), width="stretch", type="primary"):
        st.toast(t("go_pro_toast"))

key_cols = st.columns([5, 1])
with key_cols[0]:
    st.text_input(t("api_key_label"), key="api_key_input", type="password",
                  placeholder=t("api_key_placeholder"))
with key_cols[1]:
    st.markdown("<div style='height: 1.9rem;'></div>", unsafe_allow_html=True)
    if st.button(t("check_button"), width="stretch"):
        ok, msg = check_api_key(st.session_state.api_key_input)
        st.session_state.api_key_status = "valid" if ok else "invalid"
        st.session_state.api_key_message = msg
st.caption(t("api_key_tutorial_note"))

if st.session_state.api_key_status == "valid":
    st.caption(f"✅ {st.session_state.api_key_message}")
elif st.session_state.api_key_status == "invalid":
    st.caption(f"❌ {st.session_state.api_key_message}")


# ============================================================
# 9) TRUST ZONE (BANNER)
# ============================================================

st.markdown(
    f'<div class="hero-banner">'
    f'<div class="hero-pain">{t("hero_pain")}</div>'
    f'<div class="hero-headline">{t("banner")}</div>'
    f'<div class="hero-subheadline">{t("sub_banner")}</div>'
    f'</div>',
    unsafe_allow_html=True,
)


# ============================================================
# 10) STEP 1 — เลือกโครงสร้างข้อมูล
# ============================================================

st.markdown(f'<div class="zone-title">{t("step1_title")}</div>', unsafe_allow_html=True)

preset_options = [None, "meeting_notes", "product_reviews", "video_script", "raw_text_table", "custom"]
st.selectbox(t("preset_label"), preset_options, key="preset_choice",
             format_func=make_preset_formatter(st.session_state.lang, st.session_state.is_pro),
             on_change=on_preset_change)

current_choice = st.session_state.preset_choice

if current_choice is None:
    st.info(t("preset_placeholder_hint"))
elif current_choice == "custom" and not st.session_state.is_pro:
    st.markdown(
        f'<div class="locked-card"><div class="locked-title">{t("pro_locked_title")}</div>'
        f'<div class="locked-desc">{t("pro_locked_desc")}</div></div>',
        unsafe_allow_html=True,
    )
elif current_choice == "custom" and st.session_state.is_pro:
    st.markdown(f'<div class="pro-badge">{t("pro_builder_title")}</div>', unsafe_allow_html=True)
    for fid in st.session_state.custom_field_ids:
        fkey = f"cf_{fid}"
        if fkey not in st.session_state:
            st.session_state[fkey] = ""
        c1, c2 = st.columns([6, 1])
        with c1:
            st.text_input("field_name", key=fkey, label_visibility="collapsed",
                          placeholder=t("field_name_placeholder"))
        with c2:
            st.button(t("remove_field_button"), key=f"remove_{fid}",
                      on_click=remove_custom_field, args=(fid,), width="stretch")
    st.button(t("add_field_button"), on_click=add_custom_field)
else:
    preset = PRESETS[current_choice]
    lang = st.session_state.lang
    st.caption(t("locked_fields_title"))
    rows_html = ""
    for f in preset["fields"]:
        desc = f["desc_th"] if lang == "TH" else f["desc_en"]
        rows_html += f'<div class="field-row"><span class="field-chip">{f["name"]}</span><span class="field-desc">{desc}</span></div>'
    st.markdown(f'<div class="schema-card">{rows_html}</div>', unsafe_allow_html=True)
    st.caption(t("upsell_text"))


# ============================================================
# 11) STEP 2 — ป้อนข้อความและสั่งประมวลผล
# ============================================================

st.markdown(f'<div class="zone-title">{t("step2_title")}</div>', unsafe_allow_html=True)

char_limit = PRO_CHAR_LIMIT if st.session_state.is_pro else FREE_CHAR_LIMIT
st.text_area(t("text_area_label"), key="raw_text_input", height=180, max_chars=char_limit,
             placeholder=t("text_area_placeholder"), label_visibility="collapsed")
st.markdown(
    f'<div class="char-counter">{len(st.session_state.raw_text_input)} / {char_limit} {t("char_counter")}</div>',
    unsafe_allow_html=True,
)

convert_disabled = current_choice is None or (current_choice == "custom" and not st.session_state.is_pro)
col_a, col_b = st.columns([1, 2])
with col_a:
    if current_choice not in (None, "custom"):
        st.button(t("sample_button"), on_click=use_sample_text, width="stretch")
with col_b:
    convert_clicked = st.button(t("convert_button"), type="primary",
                                 width="stretch", disabled=convert_disabled)

if convert_clicked:
    with st.spinner(t("converting_status")):
        do_convert()


# ============================================================
# 12) REWARD ZONE — ผลลัพธ์
# ============================================================

if st.session_state.last_error:
    st.error(st.session_state.last_error)
    if st.session_state.last_raw_response:
        with st.expander(t("show_raw_response")):
            st.code(st.session_state.last_raw_response)

if st.session_state.last_records:
    seconds = round(st.session_state.last_elapsed or 0, 1)
    mock_note = f" ({t('mock_note')})" if st.session_state.last_is_mock else ""
    st.markdown(
        f'<div class="success-banner">{t("success_banner").format(seconds=seconds)}{mock_note}</div>',
        unsafe_allow_html=True,
    )

    fields_used = st.session_state.last_fields or get_active_fields()
    tab1, tab2, tab3 = st.tabs([t("tab_table"), t("tab_json"), t("tab_export")])

    with tab1:
        st.dataframe(pd.DataFrame(st.session_state.last_records), width="stretch", hide_index=True)
        with st.expander(t("copy_table_expander")):
            tsv_str = pd.DataFrame(st.session_state.last_records).to_csv(sep="\t", index=False)
            table_html = wrap_html_for_clipboard(
                records_to_html_table(st.session_state.last_records, fields_used)
            )
            render_dual_copy_button(table_html, tsv_str, t("copy_button_table"), "tbl_copy")
            st.caption(t("helper_copy_table_md"))
            st.code(tsv_str, language=None)

    with tab2:
        json_str = json.dumps(st.session_state.last_records, ensure_ascii=False, indent=2)
        render_copy_button(json_str, t("copy_button_json"), "json_copy")
        st.caption(t("helper_copy_json"))
        st.code(json_str, language="json")

    with tab3:
        csv_bytes = pd.DataFrame(st.session_state.last_records).to_csv(index=False).encode("utf-8-sig")
        st.download_button(t("download_csv"), data=csv_bytes, file_name="extracted_data.csv",
                            mime="text/csv", width="stretch")
        st.caption(t("helper_download_csv"))
        md_str = records_to_markdown(st.session_state.last_records, fields_used)
        render_copy_button(md_str, t("copy_button_markdown"), "md_copy")
        st.caption(t("helper_copy_markdown_obsidian"))
        st.code(md_str, language="markdown")
        st.divider()
        if st.session_state.is_pro:
            st.text_input(t("webhook_url_label"), key="webhook_url_input",
                          placeholder="https://hook.make.com/...")
            st.button(t("webhook_send_button"), on_click=send_to_webhook)
        else:
            st.info(t("webhook_pro_locked"))


# ============================================================
# 13) CONVERSION ZONE — ปลดล็อก Pro
# ============================================================

st.divider()
st.markdown(f'<div class="zone-title">{t("conversion_title")}</div>', unsafe_allow_html=True)

if st.session_state.is_pro:
    st.success(t("pro_active_badge"))
else:
    if not GUMROAD_PRODUCT_ID:
        st.caption(f"⚠️ {t('license_not_configured')}")
    lic_col1, lic_col2 = st.columns([3, 1])
    with lic_col1:
        st.text_input(t("license_key_label"), key="license_key_input",
                      placeholder=t("license_key_placeholder"), label_visibility="collapsed")
    with lic_col2:
        st.button(t("activate_button"), type="primary", width="stretch", on_click=activate_pro)
    if st.session_state.license_message:
        icon = "✅" if st.session_state.is_pro else "❌"
        st.caption(f"{icon} {st.session_state.license_message}")
st.divider()
st.markdown("### ⚙️ API Service (สำหรับสาย Automation)")

# เช็กว่าเป็น Pro หรือไม่ (ถ้าใช่ ให้แสดงระบบ / ถ้าไม่ใช่ ให้ล็อก)
if st.session_state.is_pro:
    st.markdown("เชื่อมต่อกับ Make.com / Zapier เพื่อแปลงข้อมูลอัตโนมัติ 24 ชม.")

    # ถ้ายังไม่มี Key
    if st.session_state.app_api_key is None:
        st.info("คุณยังไม่ได้สร้าง App API Key สำหรับเชื่อมต่อระบบภายนอก")
        if st.button("⚡ Generate App API Key", type="primary"):
            # สุ่มสร้าง Key ใหม่
            st.session_state.app_api_key = "sk_live_" + secrets.token_hex(16)
            st.rerun() # รีเฟรชหน้าเว็บเพื่อให้แสดง Key
            
    # ถ้ามี Key แล้ว
    else:
        st.success("✅ App API Key ของคุณพร้อมใช้งานแล้ว (อย่าแชร์ให้ผู้อื่น!)")
        # แสดง Key ในกล่องข้อความให้ก๊อปปี้ง่ายๆ
        st.code(st.session_state.app_api_key, language="bash")
        
        # ปุ่มลบ/รีเซ็ต Key กรณีทำหลุด
        if st.button("🗑️ Revoke Key (ลบและสร้างใหม่)"):
            st.session_state.app_api_key = None
            st.rerun()

        # คู่มืออธิบายให้ลูกค้าก๊อปไปตั้งค่าใน Make/Zapier
        with st.expander("📖 วิธีตั้งค่าใน Make.com / Zapier (Click เพื่อดู)"):
            st.markdown(f"""
            ในการตั้งค่า HTTP Module ให้ระบุข้อมูลดังนี้:
            
            **1. URL:** `https://api.yourdomain.com/v1/extract` *(แก้ไขเป็น URL API จริงของเราทีหลัง)*
            **2. Method:** `POST`
            **3. Headers (สำคัญมาก):**
            ต้องแนบ Key ทั้ง 2 ตัว เพื่อความปลอดภัยและเพื่อใช้โควตา AI ของคุณเอง
            - `X-App-Key`: `{st.session_state.app_api_key}`
            - `X-Anthropic-Key`: `sk-ant-xxxxxxxxxxxxxxx` *(ใส่ Anthropic API Key ของคุณ)*
            - `Content-Type`: `application/json`
            
            **4. Body (รูปแบบ JSON):**
            ```json
            {{
              "text": "ข้อความยาวๆ ที่ต้องการแปลง...",
              "preset": "meeting_notes"
            }}
            ```
            """)
else:
    # กรณีไม่ใช่ Pro (หรือปิด Dev Bypass อยู่)
    st.warning("🔒 ฟีเจอร์ API Service (เชื่อมต่อ Make/Zapier) เป็นฟีเจอร์สำหรับสมาชิก Pro เท่านั้น")
