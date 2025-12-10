import streamlit as st
from playwright.sync_api import sync_playwright
import google.generativeai as genai
import time
import os
import subprocess
from urllib.parse import unquote

# --- إعداد الصفحة ---
st.set_page_config(page_title="GMap Analyst V11", page_icon="☢️", layout="wide")

@st.cache_resource
def setup():
    # إجراء احتياطي: تثبيت تعريفات المتصفح إذا لم تكن موجودة
    if not os.path.exists("packages.txt"):
        try:
            subprocess.run(["playwright", "install", "chromium"], check=False)
        except:
            pass
setup()

st.title("☢️ أداة التحليل الشامل (الحل النهائي)")
st.caption("تقنية السحب باستخدام متصفح النظام + تحليل Gemini 1.5 Flash")

with st.sidebar:
    st.header("الإعدادات")
    gemini_key = st.text_input("مفتاح Gemini API", type="password")
    st.info("تأكد من وجود ملف packages.txt في GitHub ليعمل هذا الكود.")

raw_url = st.text_input("🔗 رابط المنافس (استخدم الرابط الطويل من المتصفح):")

# --- دوال المعالجة ---

def clean_url_smart(url):
    """تنظيف الرابط لضمان الفتح الصحيح"""
    try:
        decoded = unquote(url)
        if "/data=" in decoded: decoded = decoded.split("/data=")[0]
        if ",17z" in decoded: decoded = decoded.split(",17z")[0] + ",17z"
        return decoded
    except: return url

def get_data_blind(target_url):
    """
    استراتيجية السحب باستخدام متصفح النظام (System Browser)
    لتفادي أخطاء الانهيار على Streamlit Cloud
    """
    with sync_playwright() as p:
        # مسار متصفح كروم المثبت عبر packages.txt
        system_browser_path = "/usr/bin/chromium"
        
        browser = None
        try:
            # المحاولة الأولى: استخدام متصفح النظام (الأكثر استقراراً)
            browser = p.chromium.launch(
                executable_path=system_browser_path,
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-gpu',
                    '--disable-dev-shm-usage',
                    '--disable-setuid-sandbox'
                ]
            )
        except Exception as e:
            # المحاولة الثانية: استخدام المتصفح الافتراضي (Fallback)
            print(f"فشل استخدام متصفح النظام، جاري تجربة المتصفح المدمج: {e}")
            try:
                browser = p.chromium.launch(
                    headless=True,
                    args=['--no-sandbox', '--disable-gpu']
                )
            except Exception as e2:
                st.error(f"فشل تشغيل المتصفح تماماً: {e2}")
                return None

        # استخدام وضع الموبايل لتخفيف الصفحة
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Linux; Android 10; SM-A205U) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.101 Mobile Safari/537.36"
        )
        page = context.new_page()
        
        try:
            clean_link = clean_url_smart(target_url)
            
            # الذهاب للصفحة
            page.goto(clean_link, timeout=60000, wait_until='domcontentloaded')
            
            # انتظار "أعمى" للتأكد من تحميل النصوص
            time.sleep(5)
            
            # محاولة تخطي الكوكيز
            try:
                page.locator("button").get_by_text("Accept all").click(timeout=2000)
            except: pass

            # سحب النص بالكامل من الصفحة
            full_text = page.inner_text("body")
            
            # تنظيف بسيط للنص (حذف الأسطر الفارغة)
            clean_text = "\n".join([line for line in full_text.split('\n') if line.strip()])
            
            return clean_text[:8000] # نأخذ أول 8000 حرف

        except Exception as e:
            st.error(f"حدث خطأ أثناء قراءة الصفحة: {e}")
            return None
        finally:
            if browser:
                browser.close()

def ai_analyze_raw_text(api_key, raw_text):
    genai.configure(api_key=api_key)
    
    # استخدام الموديل السريع
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    prompt = f"""
    أمامك نص خام تم سحبه من صفحة Google Maps لنشاط تجاري.
    النص غير مرتب ويحتوي على كل شيء (قوائم، مراجعات، وصف).
    
    النص الخام:
    '''
    {raw_text}
    '''
    
    مهمتك استخراج تقرير منظم باللغة العربية:
    1. **اسم النشاط**: (استنتجه من النص).
    2. **التصنيف الدقيق**: (ابحث عن كلمات مثل "متجر"، "عيادة"، "شركة" وتفاصيلها).
    3. **الخدمات والمنتجات**: (ماذا يبيعون؟ هل يوجد توصيل؟).
    4. **تحليل المراجعات**: (ما هي نقاط القوة والضعف بناءً على آراء الناس المذكورة في النص؟).
    5. **5 كلمات مفتاحية**: (مقترحة للـ SEO).
    """
    
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"خطأ في تحليل Gemini: {e}"

# --- التشغيل الرئيسي ---
if st.button("🚀 تحليل عميق") and raw_url and gemini_key:
    with st.spinner("جاري سحب النص الكامل للصفحة (Blind Scan)..."):
        text_data = get_data_blind(raw_url)
        
        if text_data:
            st.success("تم سحب محتوى الصفحة بنجاح!")
            
            # عرض جزء من النص للمراجعة (اختياري)
            with st.expander("عرض النص الخام المستخرج"):
                st.text(text_data[:1000] + "...")
            
            st.divider()
            
            with st.spinner("جاري تحليل البيانات بواسطة Gemini 1.5 Flash..."):
                report = ai_analyze_raw_text(gemini_key, text_data)
                st.markdown(report)
