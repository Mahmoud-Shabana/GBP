import streamlit as st
from playwright.sync_api import sync_playwright
import google.generativeai as genai
import time
import os
import subprocess
from urllib.parse import unquote

# --- إعداد الصفحة ---
st.set_page_config(page_title="GMap Fast Analyst", page_icon="⚡", layout="wide")

# إعداد البيئة (تثبيت كروم لو مش موجود)
@st.cache_resource
def setup_env():
    if not os.path.exists("packages.txt"):
        try:
            subprocess.run(["playwright", "install", "chromium"], check=False)
        except: pass
setup_env()

st.title("⚡ المفتش السريع (وضع النصوص فقط)")
st.caption("يقوم بحظر الصور والخرائط لضمان التحميل السريع جداً")

with st.sidebar:
    gemini_key = st.text_input("مفتاح Gemini API", type="password")

raw_url = st.text_input("🔗 رابط المنافس:")

# --- دوال المعالجة ---

def get_data_turbo(target_url):
    with sync_playwright() as p:
        # 1. إعداد المتصفح
        executable_path = "/usr/bin/chromium"
        try:
            browser = p.chromium.launch(
                executable_path=executable_path,
                headless=True,
                args=['--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage']
            )
        except:
            # لو فشل المسار نستخدم الافتراضي
            browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-gpu'])

        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        # 🔥 الخطوة السحرية: منع تحميل الصور والخرائط والخطوط
        # ده هيحل مشكلة الـ Timeout بنسبة 100% إن شاء الله
        page.route("**/*", lambda route: route.abort() 
                   if route.request.resource_type in ["image", "media", "font", "stylesheet", "other"] 
                   else route.continue_())
        
        try:
            # تنظيف الرابط
            if "/data=" in target_url: target_url = target_url.split("/data=")[0]
            
            # الذهاب للصفحة (المفروض تفتح في ثواني لأنها بدون صور)
            # نستخدم wait_until='commit' يعني "أول ما تتصل بالسيرفر كمل شغل متستناش التحميل"
            page.goto(target_url, timeout=60000, wait_until='commit')
            
            # انتظار بسيط للنصوص
            page.wait_for_selector("h1", state="attached", timeout=20000)
            
            # محاولة تخطي الكوكيز
            try: page.locator("button").get_by_text("Accept all").click(timeout=1000)
            except: pass

            # سحب النص فوراً
            full_text = page.inner_text("body")
            
            # تنظيف النص
            clean_text = "\n".join([line for line in full_text.split('\n') if line.strip()])
            
            return clean_text[:12000] # كمية نص كافية

        except Exception as e:
            st.error(f"خطأ أثناء السحب: {e}")
            return None
        finally:
            browser.close()

def ai_analyze(api_key, text):
    genai.configure(api_key=api_key)
    models = ['gemini-1.5-flash', 'gemini-pro']
    
    prompt = f"""
    لديك نص خام تم سحبه من صفحة Google Maps (وضع النصوص فقط).
    النص:
    '''
    {text}
    '''
    
    استخرج تقرير عربي احترافي:
    1. اسم النشاط والتصنيف الدقيق.
    2. الخدمات التي يقدمها (استنتجها من الكلام).
    3. نقاط القوة والضعف (من المراجعات المذكورة في النص).
    4. 5 كلمات مفتاحية (SEO Keywords).
    """
    
    for m in models:
        try:
            model = genai.GenerativeModel(m)
            return model.generate_content(prompt).text
        except: continue
    return "فشل الاتصال بـ Gemini."

# --- التشغيل ---
if st.button("🚀 تحليل فوري") and raw_url and gemini_key:
    with st.spinner("جاري سحب النصوص فقط (بدون خرائط)..."):
        text_data = get_data_turbo(raw_url)
        
        if text_data:
            st.success("تم سحب البيانات!")
            with st.expander("عرض النص الخام"):
                st.text(text_data[:1000])
            st.divider()
            with st.spinner("جاري التحليل..."):
                report = ai_analyze(gemini_key, text_data)
                st.markdown(report)
