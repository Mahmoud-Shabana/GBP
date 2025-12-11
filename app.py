import streamlit as st
from playwright.sync_api import sync_playwright
import google.generativeai as genai
import time
import os
import subprocess
from urllib.parse import unquote

st.set_page_config(page_title="GMap Debugger V16", page_icon="🐞", layout="wide")

# تثبيت المتصفح
@st.cache_resource
def setup_env():
    if not os.path.exists("packages.txt"):
        try:
            subprocess.run(["playwright", "install", "chromium"], check=False)
        except: pass
setup_env()

st.title("🐞 المفتش (وضع التشخيص بالصور)")
st.warning("هذه النسخة ستلتقط صورة للشاشة لنتأكد مما يراه الروبوت.")

with st.sidebar:
    gemini_key = st.text_input("مفتاح Gemini API", type="password")

raw_url = st.text_input("🔗 رابط المنافس:")

def clean_url_smart(url):
    try:
        decoded = unquote(url)
        if "/data=" in decoded: decoded = decoded.split("/data=")[0]
        if ",17z" in decoded: decoded = decoded.split(",17z")[0] + ",17z"
        return decoded
    except: return url

def get_data_debug(target_url):
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

        result = {"text": "", "screenshot": None, "status": "init"}

        try:
            clean_link = clean_url_smart(target_url)
            st.toast("جاري فتح الصفحة...")
            
            # الذهاب للصفحة
            page.goto(clean_link, timeout=60000, wait_until='domcontentloaded')
            
            # الانتظار 5 ثواني
            time.sleep(5)
            
            # محاولة التقاط صورة للشاشة (عشان نشوف المشكلة)
            try:
                screenshot = page.screenshot()
                result["screenshot"] = screenshot
            except: pass

            # سحب النص
            full_text = page.inner_text("body")
            # تنظيف الفراغات
            clean_text = "\n".join([line.strip() for line in full_text.split('\n') if line.strip()])
            
            result["text"] = clean_text
            result["length"] = len(clean_text)
            
            return result

        except Exception as e:
            st.error(f"حدث خطأ أثناء التشخيص: {e}")
            return None
        finally:
            browser.close()

def ai_analyze(api_key, text):
    genai.configure(api_key=api_key)
    # تجربة الموديلات بالترتيب
    models = ['gemini-1.5-flash', 'gemini-pro']
    
    prompt = f"""
    نص خام من خرائط جوجل:
    '''{text}'''
    
    استخرج تقرير:
    1. اسم النشاط.
    2. التصنيف.
    3. الخدمات.
    4. نقاط القوة/الضعف.
    5. كلمات مفتاحية.
    """
    for m in models:
        try:
            model = genai.GenerativeModel(m)
            return model.generate_content(prompt).text
        except: continue
    return "فشل التحليل."

# --- التشغيل ---
if st.button("🚀 تشخيص المشكلة") and raw_url and gemini_key:
    with st.spinner("جاري السحب والتصوير..."):
        data = get_data_debug(raw_url)
        
        if data:
            # عرض الصورة (الدليل القاطع)
            if data["screenshot"]:
                st.image(data["screenshot"], caption="ما يراه الروبوت الآن", use_container_width=True)
            
            # عرض طول النص
            st.metric("حجم البيانات المسحوبة", f"{data.get('length', 0)} حرف")
            
            # عرض النص الخام إجبارياً
            if data["length"] < 100:
                st.error("⚠️ النص المسحوب قصير جداً! انظر للصورة أعلاه لتعرف السبب (هل هي صفحة بيضاء؟ هل يوجد تحقق بشري؟).")
                st.code(data["text"]) # عرض النص القليل الموجود
            else:
                st.success("تم سحب بيانات كافية.")
                with st.expander("عرض النص الخام كاملاً"):
                    st.text(data["text"])
                
                st.divider()
                with st.spinner("جاري التحليل..."):
                    report = ai_analyze(gemini_key, data["text"])
                    st.markdown(report)
