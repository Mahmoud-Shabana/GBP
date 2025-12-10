import streamlit as st
from playwright.sync_api import sync_playwright
import google.generativeai as genai
import time
import os
import subprocess
from urllib.parse import unquote

# --- إعداد الصفحة ---
st.set_page_config(page_title="GMap Analyst V10", page_icon="☢️", layout="wide")

@st.cache_resource
def setup():
    if not os.path.exists("packages.txt"):
        subprocess.run(["playwright", "install", "chromium"], check=False)
setup()

st.title("☢️ أداة التحليل الشامل (الحل النهائي)")
st.caption("تقنية سحب النص الكامل + تحليل Gemini 1.5 Flash")

with st.sidebar:
    gemini_key = st.text_input("مفتاح Gemini API", type="password")
    
raw_url = st.text_input("🔗 رابط المنافس (استخدم الرابط الطويل):")

def clean_url_smart(url):
    try:
        decoded = unquote(url)
        if "/data=" in decoded: decoded = decoded.split("/data=")[0]
        if ",17z" in decoded: decoded = decoded.split(",17z")[0] + ",17z"
        return decoded
    except: return url

def get_data_blind(target_url):
    """
    استراتيجية السحب الأعمى:
    لا نبحث عن عناصر محددة، بل نسحب كل النص الظاهر في الصفحة.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-gpu'])
        # نستخدم موبايل أندرويد عشان الصفحة تكون خفيفة والنص واضح
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Linux; Android 10; SM-A205U) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.101 Mobile Safari/537.36"
        )
        page = context.new_page()
        
        try:
            clean_link = clean_url_smart(target_url)
            # انتظار التحميل
            page.goto(clean_link, timeout=60000, wait_until='domcontentloaded')
            
            # ننتظر 6 ثواني "عمياني" عشان نضمن إن النصوص ظهرت
            time.sleep(6)
            
            # محاولة بسيطة لتوسيع المراجعات لو زرار "المزيد" موجود
            try:
                page.locator("button").get_by_text("More").click(timeout=2000)
            except: pass

            # 🔥 اللقطة الحاسمة: سحب كل نص الصفحة
            # بنقوله: هات كل كلمة مكتوبة في الـ body
            full_text = page.inner_text("body")
            
            # تنظيف النص من الفراغات الزيادة
            clean_text = "\n".join([line for line in full_text.split('\n') if line.strip()])
            
            return clean_text[:8000] # نأخذ أول 8000 حرف (كافية جداً للتحليل)

        except Exception as e:
            st.error(f"خطأ في السحب: {e}")
            return None
        finally:
            browser.close()

def ai_analyze_raw_text(api_key, raw_text):
    genai.configure(api_key=api_key)
    
    # استخدام الموديل الأحدث حصراً
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    prompt = f"""
    أمامك "نص خام" تم سحبه من صفحة نشاط تجاري على Google Maps. النص قد يكون غير مرتب.
    
    النص الخام:
    '''
    {raw_text}
    '''
    
    مهمتك استخراج المعلومات التالية بدقة وتحليلها:
    1. **اسم النشاط**: (استخرجه من النص).
    2. **التصنيف الدقيق**: (ابحث في النص عن كلمات زي "Medical supply store", "متجر", "شركة").
    3. **الخدمات المذكورة**: (ماذا يبيعون؟ هل هناك توصيل؟ جملة؟ تجزئة؟).
    4. **نقاط القوة/الضعف**: (حلل أي جمل تبدو كآراء عملاء أو تقييمات).
    5. **كلمات مفتاحية**: 5 كلمات قوية للـ SEO.
    
    اكتب التقرير باللغة العربية بتنسيق منظم.
    """
    
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"خطأ في Gemini: {e}"

# --- التشغيل ---
if st.button("🚀 تحليل عميق") and raw_url and gemini_key:
    with st.spinner("جاري سحب الصفحة بالكامل (Blind Scraping)..."):
        text_data = get_data_blind(raw_url)
        
        if text_data:
            st.success("تم سحب النص الخام بنجاح!")
            
            with st.expander("عرض النص الخام المستخرج (للمراجعة)"):
                st.text(text_data[:1000] + "...")
            
            st.divider()
            
            with st.spinner("Gemini يقوم بتحليل البيانات الآن..."):
                report = ai_analyze_raw_text(gemini_key, text_data)
                st.markdown(report)
