import streamlit as st
from playwright.sync_api import sync_playwright
import google.generativeai as genai
import time
import os
import subprocess
from urllib.parse import unquote

# --- إعداد الصفحة ---
st.set_page_config(page_title="GMap Validator V14", page_icon="✅", layout="wide")

# تثبيت المتصفح
@st.cache_resource
def setup_env():
    if not os.path.exists("packages.txt"):
        try:
            subprocess.run(["playwright", "install", "chromium"], check=False)
        except: pass
setup_env()

st.title("✅ المفتش الذكي (مع مصحح الروابط)")
st.info("هذه النسخة تفحص الرابط قبل البدء لتجنب الأخطاء.")

with st.sidebar:
    gemini_key = st.text_input("مفتاح Gemini API", type="password")

raw_url = st.text_input("🔗 رابط المنافس (تأكد أنه يبدأ بـ https://www.google.com/maps...):")

def validate_and_clean_url(url):
    """
    وظيفة لتنظيف الرابط ورفض الروابط التالفة
    """
    if not url: return None
    
    # 1. رفض روابط googleusercontent لأنها تسبب أخطاء Protocol Error
    if "googleusercontent.com" in url:
        st.error("⛔ توقف! الرابط الذي تستخدمه (googleusercontent) هو رابط تالف أو مؤقت.")
        st.warning("👉 الحل: افتح الخريطة في متصفحك، وانتظر التحميل، ثم انسخ الرابط من شريط العنوان الذي يبدأ بـ https://www.google.com/maps")
        return None

    try:
        decoded = unquote(url)
        # تنظيف الذيل
        if "/data=" in decoded: decoded = decoded.split("/data=")[0]
        if ",17z" in decoded: decoded = decoded.split(",17z")[0] + ",17z"
        return decoded
    except: return url

def get_data_validated(target_url):
    with sync_playwright() as p:
        executable_path = "/usr/bin/chromium"
        try:
            browser = p.chromium.launch(executable_path=executable_path, headless=True, args=['--no-sandbox', '--disable-gpu'])
        except:
            browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-gpu'])

        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        try:
            # الذهاب للصفحة
            page.goto(target_url, timeout=60000, wait_until='domcontentloaded')
            
            # الانتظار حتى يظهر الاسم
            try:
                page.wait_for_selector("h1", state="attached", timeout=15000)
            except:
                st.warning("⚠️ الصفحة بطيئة، سنحاول سحب البيانات المتاحة...")

            # سحب النص
            full_text = page.inner_text("body")
            
            # تنظيف
            clean_text = "\n".join([line.strip() for line in full_text.split('\n') if line.strip()])
            return clean_text[:15000]

        except Exception as e:
            st.error(f"خطأ المتصفح: {e}")
            return None
        finally:
            browser.close()

def ai_analyze(api_key, text):
    genai.configure(api_key=api_key)
    # استخدام gemini-pro فقط لأنه الأضمن حالياً
    model = genai.GenerativeModel('gemini-pro')
    
    prompt = f"""
    نص خام من خرائط جوجل:
    '''{text}'''
    
    استخرج تقرير عربي:
    1. اسم النشاط.
    2. التصنيف.
    3. الخدمات.
    4. نقاط القوة/الضعف.
    5. 5 كلمات مفتاحية.
    """
    try:
        return model.generate_content(prompt).text
    except Exception as e:
        return f"خطأ Gemini: {e}"

# --- التشغيل ---
if st.button("🚀 فحص وتحليل") and raw_url and gemini_key:
    # 1. فحص الرابط أولاً
    valid_url = validate_and_clean_url(raw_url)
    
    if valid_url:
        st.write(f"✅ الرابط سليم، جاري الاتصال: {valid_url[:60]}...")
        with st.spinner("جاري سحب البيانات..."):
            text_data = get_data_validated(valid_url)
            
            if text_data:
                # التحقق من أننا لم نسحب صفحة عامة
                if "Restaurants" in text_data[:300] and len(text_data) < 1000:
                    st.error("⚠️ الرابط فتح صفحة عامة! تأكد من نسخ رابط المحل بدقة.")
                else:
                    st.success("تم السحب بنجاح!")
                    st.divider()
                    with st.spinner("جاري التحليل..."):
                        report = ai_analyze(gemini_key, text_data)
                        st.markdown(report)
