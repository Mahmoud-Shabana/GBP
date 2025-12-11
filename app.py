import streamlit as st
from playwright.sync_api import sync_playwright
import google.generativeai as genai
import time
import os
import subprocess
from urllib.parse import unquote

# --- إعداد الصفحة ---
st.set_page_config(page_title="GMap Analyst Stable", page_icon="⚖️", layout="wide")

# محاولة تثبيت المتصفح (إجراء احتياطي)
@st.cache_resource
def setup_env():
    if not os.path.exists("packages.txt"):
        try:
            subprocess.run(["playwright", "install", "chromium"], check=False)
        except: pass
setup_env()

st.title("⚖️ المفتش المستقر (Gemini Pro + Full Load)")
st.caption("يعتمد على التحميل الكامل للصفحة لضمان الدقة + موديل Pro المتوافق مع الجميع")

with st.sidebar:
    gemini_key = st.text_input("مفتاح Gemini API", type="password")
    st.info("💡 نصيحة: إذا تأخر التحميل، اصبر قليلاً، الدقة أهم من السرعة.")

raw_url = st.text_input("🔗 رابط المنافس (الرابط الطويل):")

def clean_url_smart(url):
    try:
        decoded = unquote(url)
        # إزالة البيانات الزائدة التي قد تسبب مشاكل
        if "/data=" in decoded: decoded = decoded.split("/data=")[0]
        if ",17z" in decoded: decoded = decoded.split(",17z")[0] + ",17z"
        return decoded
    except: return url

def get_data_stable(target_url):
    with sync_playwright() as p:
        # استخدام متصفح النظام إذا وجد، أو تحميل جديد
        executable_path = "/usr/bin/chromium"
        try:
            browser = p.chromium.launch(executable_path=executable_path, headless=True, args=['--no-sandbox', '--disable-gpu'])
        except:
            browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-gpu'])

        # نستخدم User Agent لجهاز كمبيوتر عادي (Desktop) لضمان ظهور البيانات كاملة
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        try:
            clean_link = clean_url_smart(target_url)
            
            # 1. الذهاب للصفحة (بدون حظر أي ملفات هذه المرة لضمان التحميل)
            # زدنا الوقت لـ 90 ثانية تحسباً لبطء السيرفر
            page.goto(clean_link, timeout=90000, wait_until='domcontentloaded')
            
            # 2. الانتظار الذكي: لن نتحرك حتى يظهر اسم المحل (h1)
            try:
                page.wait_for_selector("h1", state="attached", timeout=20000)
            except:
                st.warning("⚠️ الصفحة تأخرت في التحميل، سنحاول سحب ما ظهر...")

            # محاولة تخطي الكوكيز
            try: page.locator("button").get_by_text("Accept all").click(timeout=2000)
            except: pass
            
            # محاولة فتح تبويب المراجعات (Reviews)
            try:
                page.locator("button[aria-label*='Reviews'], button[aria-label*='مراجعات']").first.click()
                time.sleep(3) # انتظار تحميل النصوص
            except: pass

            # 3. سحب النصوص
            full_text = page.inner_text("body")
            
            # تنظيف وتنسيق
            lines = [line.strip() for line in full_text.split('\n') if line.strip()]
            clean_text = "\n".join(lines)
            
            return clean_text[:15000]

        except Exception as e:
            st.error(f"حدث خطأ أثناء السحب: {e}")
            return None
        finally:
            browser.close()

def ai_analyze(api_key, text):
    genai.configure(api_key=api_key)
    
    # 🔥 التغيير الحاسم: استخدام gemini-pro بدلاً من flash
    # هذا الموديل يعمل على المكتبات القديمة والجديدة
    model_name = 'gemini-pro'
    
    prompt = f"""
    أنت خبير تحليل بيانات. أمامك نص خام تم سحبه من صفحة Google Maps لنشاط تجاري.
    النص قد يحتوي على قوائم وكلمات غير مرتبة.
    
    النص:
    '''
    {text}
    '''
    
    المطلوب استخراج تقرير عربي دقيق:
    1. **اسم النشاط**: (ابحث عن العنوان الرئيسي).
    2. **التصنيف**: (ابحث عن نوع النشاط مثل مطعم، شركة، مستشفى).
    3. **ملخص المراجعات**: (ماذا يقول الناس؟ نقاط إيجابية وسلبية).
    4. **الخدمات**: (ماذا يقدمون؟).
    5. **كلمات مفتاحية**: (5 كلمات SEO).
    
    إذا لم تجد معلومات كافية، قل ذلك بوضوح.
    """
    
    try:
        model = genai.GenerativeModel(model_name)
        return model.generate_content(prompt).text
    except Exception as e:
        return f"خطأ في Gemini: {e}"

# --- التشغيل ---
if st.button("🚀 تحليل مستقر") and raw_url and gemini_key:
    with st.spinner("جاري التحميل الكامل للصفحة (قد يستغرق دقيقة)..."):
        text_data = get_data_stable(raw_url)
        
        if text_data:
            # تحقق بسيط: هل سحبنا بيانات خرائط عامة أم بيانات محل؟
            if "Restaurants" in text_data[:500] and "Hotels" in text_data[:500] and len(text_data) < 2000:
                st.warning("⚠️ تنبيه: يبدو أن الرابط فتح خريطة عامة ولم يفتح المحل المحدد. تأكد من استخدام الرابط الطويل المباشر للمحل.")
                with st.expander("عرض النص المسحوب"):
                    st.text(text_data)
            else:
                st.success("تم سحب بيانات المحل بنجاح!")
                with st.expander("معاينة النص"):
                    st.text(text_data[:1000])
                
                st.divider()
                with st.spinner(f"جاري التحليل باستخدام Gemini Pro..."):
                    report = ai_analyze(gemini_key, text_data)
                    st.markdown(report)
