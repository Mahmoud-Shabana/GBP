import streamlit as st
from playwright.sync_api import sync_playwright
import google.generativeai as genai
import time
import re
import os
import subprocess
from urllib.parse import unquote

# --- إعداد الصفحة ---
st.set_page_config(page_title="المفتش الذكي (V9)", page_icon="🕵️‍♂️", layout="wide")

@st.cache_resource
def setup():
    if not os.path.exists("packages.txt"):
        subprocess.run(["playwright", "install", "chromium"], check=False)
setup()

st.title("🕵️‍♂️ المفتش الذكي: تحليل المنافسين (النسخة المنقذة)")

with st.sidebar:
    st.header("الإعدادات")
    gemini_key = st.text_input("مفتاح Gemini API", type="password")

raw_url = st.text_input("🔗 رابط المنافس:")

# --- دوال المعالجة ---

def clean_url_smart(url):
    try:
        decoded = unquote(url)
        if "/data=" in decoded: decoded = decoded.split("/data=")[0]
        if ",17z" in decoded: decoded = decoded.split(",17z")[0] + ",17z"
        return decoded
    except: return url

def get_data_rescue(target_url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-gpu'])
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        try:
            clean_link = clean_url_smart(target_url)
            page.goto(clean_link, timeout=60000, wait_until='domcontentloaded')
            
            # محاولة تخطي الكوكيز
            try: page.locator("button:has-text('Accept all')").click(timeout=3000)
            except: pass

            # انتظار ظهور أي محتوى
            try: page.wait_for_selector("h1", state="attached", timeout=15000)
            except: pass

            data = {}
            
            # 1. الاسم (محاولة من العنوان لو الـ h1 فشل)
            try:
                data['name'] = page.locator("h1").first.text_content()
            except:
                data['name'] = page.title().replace("- Google Maps", "")

            # 2. التصنيف (محاولة سحب النص المحيط بالاسم)
            # لو الزرار فشل، هناخد النص اللي تحت الاسم علطول
            try:
                data['category'] = page.locator("button[jsaction*='category']").first.text_content()
            except:
                data['category'] = "غير محدد (سيتم استخراجه بالذكاء الاصطناعي)"

            # 3. المراجعات (محاولة سحب الصفحة كلها كنص)
            # لو فشلنا في سحب زر المراجعات، سنسحب كل النصوص الظاهرة في الصفحة
            try:
                # نضغط على زر المراجعات لو موجود
                page.evaluate("document.querySelector('button[aria-label*=\"Reviews\"], button[aria-label*=\"مراجعات\"]').click()")
                time.sleep(2)
                reviews = page.locator(".wiI7pd").all_text_contents()
                data['reviews'] = " ".join(reviews)
            except:
                # الخطة البديلة: سحب نص الصفحة بالكامل (Body Text)
                data['reviews'] = page.inner_text("body")[:5000] # أول 5000 حرف

            # 4. الكود الخام
            data['raw_html'] = page.content()
            
            return data
        except Exception as e:
            st.error(f"خطأ تقني: {e}")
            return None
        finally:
            browser.close()

def smart_analysis(api_key, data):
    genai.configure(api_key=api_key)
    
    # حل مشكلة الموديل: نجرب الجديد، لو فشل نستخدم القديم
    models = ['gemini-1.5-flash', 'gemini-pro']
    
    # تحضير التصنيفات المخفية من الكود
    hidden_cats = "غير موجود"
    try:
        clean_name = re.escape(data['name'].split()[0]) # نستخدم أول كلمة من الاسم للبحث
        match = re.search(rf'\[\\"{clean_name}', data['raw_html'])
        if match:
            # استخراج عينة حول الاسم
            hidden_cats = "تم إرسال الكود للذكاء الاصطناعي لاستخراجه"
    except: pass

    prompt = f"""
    أنت خبير SEO. البيانات المستخرجة قد تكون غير مرتبة، مهمتك تنظيفها وتحليلها.
    
    البيانات الخام:
    - الاسم التقريبي: {data['name']}
    - التصنيف المبدئي: {data['category']}
    - نصوص من الصفحة (تشمل المراجعات والوصف): {data['reviews'][:4000]}
    
    المطلوب (تقرير باللغة العربية):
    1. **حدد التصنيف الدقيق:** (اقرأ النصوص واستنتج التصنيف الحقيقي للنشاط إذا كان "غير محدد").
    2. **نقاط القوة:** ماذا يمدح الناس في النصوص؟
    3. **نقاط الضعف:** ما هي المشاكل الظاهرة؟
    4. **التصنيفات المقترحة:** بناءً على نوع النشاط، ما التصنيفات التي يجب أن أضيفها؟
    """
    
    for model_name in models:
        try:
            model = genai.GenerativeModel(model_name)
            return model.generate_content(prompt).text
        except:
            continue
            
    return "فشل الاتصال بجميع موديلات Gemini. تأكد من صحة المفتاح API."

# --- التشغيل ---
if st.button("🚀 تحليل إنقاذي") and raw_url and gemini_key:
    with st.spinner("جاري سحب البيانات بأي طريقة ممكنة..."):
        result = get_data_rescue(raw_url)
        
        if result:
            st.success(f"تم سحب البيانات الخام لـ: {result['name']}")
            
            st.divider()
            with st.spinner("جاري تحليل النصوص المبعثرة بالذكاء الاصطناعي..."):
                report = smart_analysis(gemini_key, result)
                st.markdown(report)
