import streamlit as st
from playwright.sync_api import sync_playwright
import google.generativeai as genai
import time
import os
import subprocess
from urllib.parse import unquote

# --- إعداد الصفحة ---
st.set_page_config(page_title="GMap Analyst Final", page_icon="🕵️‍♂️", layout="wide")

# محاولة تثبيت المتصفح إذا لم يكن موجوداً (إجراء احتياطي)
@st.cache_resource
def setup_env():
    if not os.path.exists("packages.txt"):
        try:
            # محاولة تثبيت المكتبات الناقصة في الخلفية
            subprocess.run(["playwright", "install-deps"], check=False)
        except: pass
setup_env()

st.title("🕵️‍♂️ المفتش الذكي (النسخة النهائية)")
st.caption("يعمل باستخدام متصفح النظام Chromium لتفادي أخطاء السيرفر")

with st.sidebar:
    st.header("بيانات الدخول")
    gemini_key = st.text_input("مفتاح Gemini API", type="password")
    st.warning("⚠️ ملاحظة: تأكد من تعديل ملف packages.txt في GitHub ليحتوي على chromium فقط.")

raw_url = st.text_input("🔗 رابط المنافس (الرابط الطويل):")

# --- دوال المعالجة ---

def clean_url_smart(url):
    try:
        decoded = unquote(url)
        if "/data=" in decoded: decoded = decoded.split("/data=")[0]
        if ",17z" in decoded: decoded = decoded.split(",17z")[0] + ",17z"
        return decoded
    except: return url

def get_data_system_browser(target_url):
    """
    سحب البيانات باستخدام متصفح النظام المثبت مسبقاً
    """
    with sync_playwright() as p:
        # محاولة تحديد مسار كروم المثبت على سيرفر Streamlit
        # المسار عادة يكون هنا بعد تثبيت chromium package
        executable_path = "/usr/bin/chromium"
        
        try:
            browser = p.chromium.launch(
                executable_path=executable_path,
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-gpu',
                    '--disable-dev-shm-usage',
                    '--disable-setuid-sandbox'
                ]
            )
        except Exception as e:
            # إذا فشل المسار المحدد، نترك Playwright يحاول البحث بنفسه
            print(f"فشل تشغيل متصفح النظام، جاري المحاولة التلقائية: {e}")
            try:
                browser = p.chromium.launch(
                    headless=True,
                    args=['--no-sandbox', '--disable-gpu']
                )
            except Exception as e2:
                st.error(f"خطأ قاتل: لم يتم العثور على متصفح. {e2}")
                return None

        # استخدام سياق موبايل لتسريع التحميل
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Linux; Android 10; SM-A205U) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.101 Mobile Safari/537.36"
        )
        page = context.new_page()
        
        try:
            clean_link = clean_url_smart(target_url)
            
            # الذهاب للصفحة
            page.goto(clean_link, timeout=60000, wait_until='domcontentloaded')
            
            # انتظار 4 ثواني للتأكد من ظهور النصوص
            time.sleep(4)
            
            # محاولة تخطي زر الكوكيز
            try:
                page.locator("button").get_by_text("Accept all").click(timeout=1000)
            except: pass

            # سحب كل النصوص الموجودة في الصفحة
            full_text = page.inner_text("body")
            
            # تنظيف النص
            clean_text = "\n".join([line for line in full_text.split('\n') if line.strip()])
            
            # نأخذ جزء كافي من النص للتحليل (أول 10000 حرف)
            return clean_text[:10000]

        except Exception as e:
            st.error(f"حدث خطأ أثناء التصفح: {e}")
            return None
        finally:
            if browser:
                browser.close()

def ai_analyze(api_key, text):
    genai.configure(api_key=api_key)
    # استخدام الموديل المتوفر
    models = ['gemini-1.5-flash', 'gemini-pro']
    
    prompt = f"""
    أمامك محتوى نصي "خام" تم سحبه من صفحة Google Maps لنشاط تجاري.
    النص:
    '''
    {text}
    '''
    
    استخرج تقرير احترافي (باللغة العربية):
    1. **اسم النشاط**:
    2. **التصنيف**: (ابحث بدقة في النص).
    3. **الخدمات**: (ماذا يقدمون؟).
    4. **نقاط القوة والضعف**: (من خلال تحليل المراجعات الموجودة في النص).
    5. **اقتراحات SEO**: (5 كلمات مفتاحية).
    """
    
    for m in models:
        try:
            model = genai.GenerativeModel(m)
            return model.generate_content(prompt).text
        except:
            continue
    return "فشل الاتصال بجميع موديلات Gemini. تأكد من المفتاح."

# --- التشغيل ---
if st.button("🚀 تحليل الآن") and raw_url and gemini_key:
    with st.spinner("جاري الاتصال بالسيرفر وسحب البيانات..."):
        text_data = get_data_system_browser(raw_url)
        
        if text_data:
            st.success("تم سحب البيانات بنجاح!")
            with st.expander("عرض النص الخام"):
                st.text(text_data[:1000])
            
            st.divider()
            with st.spinner("جاري التحليل بالذكاء الاصطناعي..."):
                report = ai_analyze(gemini_key, text_data)
                st.markdown(report)
