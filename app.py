import streamlit as st
from playwright.sync_api import sync_playwright
import google.generativeai as genai
import time
import re
import os
import subprocess
from urllib.parse import unquote

# --- إعداد الصفحة ---
st.set_page_config(page_title="المفتش الذكي - GMap Inspector", page_icon="🕵️‍♂️", layout="wide")

# تثبيت المتصفح بصمت عند البدء
@st.cache_resource
def setup():
    if not os.path.exists("packages.txt"):
        subprocess.run(["playwright", "install", "chromium"], check=False)
setup()

st.title("🕵️‍♂️ المفتش الذكي: تحليل المنافسين")
st.markdown("تحليل نقاط القوة والضعف، التصنيفات المخفية، والخدمات.")

with st.sidebar:
    st.header("إعدادات المفتش")
    gemini_key = st.text_input("مفتاح Gemini API", type="password")
    st.info("💡 نصيحة: استخدم الرابط الطويل من المتصفح لضمان أدق النتائج.")

raw_url = st.text_input("🔗 رابط المنافس (URL):")

# --- دوال المعالجة ---

def clean_url_smart(url):
    """تنظيف الرابط لضمان وصول الروبوت"""
    try:
        decoded = unquote(url)
        if "/data=" in decoded: decoded = decoded.split("/data=")[0]
        if ",17z" in decoded: decoded = decoded.split(",17z")[0] + ",17z"
        return decoded
    except: return url

def get_data_deep(target_url):
    """سحب البيانات + الكود المصدري"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-gpu'])
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        try:
            clean_link = clean_url_smart(target_url)
            # نستخدم domcontentloaded للسرعة
            page.goto(clean_link, timeout=60000, wait_until='domcontentloaded')
            
            # محاولة تخطي الكوكيز
            try: page.locator("button:has-text('Accept all')").click(timeout=2000)
            except: pass

            page.wait_for_selector("h1", timeout=20000)

            data = {}
            data['name'] = page.locator("h1").first.inner_text()
            
            # التصنيف الظاهر
            try:
                data['category'] = page.locator("button[jsaction*='category']").first.inner_text()
            except:
                data['category'] = "غير محدد"

            # المراجعات (أهم مصدر لمعرفة الخدمات ونقاط القوة)
            data['reviews'] = ""
            try:
                page.locator("button[aria-label*='Reviews'], button[aria-label*='مراجعات']").first.click()
                time.sleep(2)
                # سحب أكبر كمية ممكنة من النصوص
                reviews = page.locator(".wiI7pd").all_inner_texts()
                data['reviews'] = " ".join(reviews)
            except: pass

            # الكود الخام (عشان ندور فيه على التصنيفات المخفية)
            data['raw_html'] = page.content()
            
            return data
        except Exception as e:
            st.error(f"خطأ أثناء الفحص: {e}")
            return None
        finally:
            browser.close()

def inspector_analysis(api_key, data):
    """العقل المدبر: يحلل كل شيء ويعطي التقرير المفصل"""
    genai.configure(api_key=api_key)
    
    # محاولة استخراج التصنيفات المخفية من الكود الأول
    hidden_cats_text = "لا توجد"
    try:
        clean_cat = re.escape(data['category'])
        # بحث سريع في الكود حول التصنيف الأساسي
        match = re.search(rf'\[\\"{clean_cat}\\"(.*?)]', data['raw_html'])
        if match:
            extracted = re.findall(r'\\"(.*?)\\"', match.group(1))
            hidden_cats_list = [c for c in extracted if len(c)>2 and not c.isdigit()]
            hidden_cats_text = ", ".join(list(set(hidden_cats_list)))
    except: pass

    # تجهيز التقرير لـ Gemini
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    prompt = f"""
    تصرف كمستشار أعمال وخبير SEO. لديك بيانات لمنافس (الاسم: {data['name']}).
    
    البيانات المستخرجة:
    1. التصنيف المعلن: {data['category']}
    2. تصنيفات مخفية محتملة في الكود: {hidden_cats_text}
    3. آراء العملاء (Raw Reviews): {data['reviews'][:3000]}
    
    المطلوب منك تحليل دقيق جداً (باللغة العربية) يجيب على هذه النقاط:
    
    أولاً: نقاط القوة (Why they are strong?) 💪
    - ما الذي يمدحه الناس بشدة؟ (السرعة؟ السعر؟ التعامل؟ جودة منتج معين؟)
    
    ثانياً: نقاط الضعف (Weaknesses & Gaps) 📉
    - ما هي المشاكل التي تكررت في الشكاوى؟ (استخرج منها فرص لي).
    
    ثالثاً: هيكل التصنيفات (Categories Structure) 🏷️
    - حلل التصنيف الأساسي والمخفي، واقترح عليّ: هل أستخدم نفس التصنيفات؟
    
    رابعاً: الخدمات الأساسية (Core Services) 🛠️
    - استنتج من كلام الناس ما هي "الخدمات الفعلية" التي يبيعها هذا المنافس بكثرة (مثلاً: هل يركز على الجملة؟ التجزئة؟ توصيل سريع؟).
    
    نسق الإجابة بشكل نقاط واضحة وجذابة.
    """
    
    try:
        return model.generate_content(prompt).text
    except Exception as e:
        return f"حدث خطأ في التحليل الذكي: {e}"

# --- واجهة التشغيل ---
if st.button("🚀 ابدأ الفحص") and raw_url and gemini_key:
    with st.spinner("جاري إرسال المفتش السري..."):
        result = get_data_deep(raw_url)
        
        if result:
            st.success(f"تم الإمساك بالهدف: {result['name']}")
            
            # عرض سريع للبيانات
            col1, col2 = st.columns(2)
            col1.metric("التصنيف الرئيسي", result['category'])
            col2.metric("حجم البيانات المحللة", f"{len(result['reviews'])} حرف")
            
            st.divider()
            
            # عرض التقرير الذكي
            with st.spinner("جاري كتابة تقرير نقاط القوة والضعف..."):
                report = inspector_analysis(gemini_key, result)
                st.markdown(report)
