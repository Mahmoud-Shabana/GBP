import streamlit as st
from playwright.sync_api import sync_playwright
import google.generativeai as genai
import time
import os
import subprocess
from urllib.parse import unquote

st.set_page_config(page_title="GMap Analyst Final", page_icon="🎯", layout="wide")

# تثبيت المتصفح عند الحاجة
@st.cache_resource
def setup_env():
    if not os.path.exists("packages.txt"):
        try:
            subprocess.run(["playwright", "install", "chromium"], check=False)
        except: pass
setup_env()

st.title("🎯 المفتش الذكي (وضع البيانات السريعة)")

with st.sidebar:
    gemini_key = st.text_input("مفتاح Gemini API", type="password")

raw_url = st.text_input("🔗 رابط المنافس:")

def get_data_balanced(target_url):
    with sync_playwright() as p:
        executable_path = "/usr/bin/chromium"
        try:
            browser = p.chromium.launch(
                executable_path=executable_path,
                headless=True,
                args=['--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage']
            )
        except:
            browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-gpu'])

        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        # 🔥 التعديل: نحظر الصور والخطوط فقط، ونسمح بالبيانات
        page.route("**/*", lambda route: route.abort() 
                   if route.request.resource_type in ["image", "media", "font"] 
                   else route.continue_())
        
        try:
            if "/data=" in target_url: target_url = target_url.split("/data=")[0]
            
            # ننتظر حتى استقرار الشبكة (networkidle) لأننا خففنا الصفحة
            page.goto(target_url, timeout=60000, wait_until='networkidle')
            
            # محاولة تخطي الكوكيز
            try: page.locator("button").get_by_text("Accept all").click(timeout=1000)
            except: pass
            
            # محاولة فتح المراجعات
            try:
                page.locator("button[aria-label*='Reviews'], button[aria-label*='مراجعات']").first.click()
                time.sleep(2)
            except: pass

            # سحب النص
            full_text = page.inner_text("body")
            clean_text = "\n".join([line for line in full_text.split('\n') if line.strip()])
            
            return clean_text[:15000]

        except Exception as e:
            st.error(f"خطأ أثناء السحب: {e}")
            return None
        finally:
            browser.close()

def ai_analyze(api_key, text):
    genai.configure(api_key=api_key)
    # استخدام الموديل الأحدث
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    prompt = f"""
    لديك نص خام من صفحة نشاط تجاري (يحتوي على اسم، تصنيف، ومراجعات).
    
    النص:
    '''
    {text}
    '''
    
    استخرج تقرير عربي دقيق:
    1. اسم النشاط.
    2. التصنيف الظاهر.
    3. الخدمات المستنتجة.
    4. نقاط القوة والضعف (من المراجعات).
    5. 5 كلمات مفتاحية.
    """
    
    try:
        return model.generate_content(prompt).text
    except Exception as e:
        return f"خطأ في Gemini: {e} (تأكد أن المفتاح صحيح وأن المكتبة محدثة)"

if st.button("🚀 تحليل") and raw_url and gemini_key:
    with st.spinner("جاري سحب البيانات (بدون صور)..."):
        text_data = get_data_balanced(raw_url)
        
        if text_data:
            st.success("تم السحب!")
            with st.expander("معاينة النص"):
                st.text(text_data[:1000])
            st.divider()
            with st.spinner("جاري التحليل..."):
                report = ai_analyze(gemini_key, text_data)
                st.markdown(report)
