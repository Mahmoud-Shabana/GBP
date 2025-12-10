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

@st.cache_resource
def setup():
    if not os.path.exists("packages.txt"):
        subprocess.run(["playwright", "install", "chromium"], check=False)
setup()

st.title("🕵️‍♂️ المفتش الذكي: تحليل المنافسين")

with st.sidebar:
    st.header("إعدادات المفتش")
    gemini_key = st.text_input("مفتاح Gemini API", type="password")

raw_url = st.text_input("🔗 رابط المنافس (URL):")

# --- دوال المعالجة ---

def clean_url_smart(url):
    try:
        decoded = unquote(url)
        if "/data=" in decoded: decoded = decoded.split("/data=")[0]
        if ",17z" in decoded: decoded = decoded.split(",17z")[0] + ",17z"
        return decoded
    except: return url

def get_data_deep(target_url):
    with sync_playwright() as p:
        # إعدادات متصفح قوية لتخطي الحجب
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
            try: page.locator("button:has-text('Accept all')").click(timeout=3000)
            except: pass

            # 🔥 التعديل الجوهري هنا:
            # state="attached" تعني: لا يهمني إن كان ظاهراً، المهم أنه موجود في الكود
            try:
                page.wait_for_selector("h1", state="attached", timeout=20000)
                # text_content يقرأ النص حتى لو كان مخفياً (Hidden)
                name = page.locator("h1").first.text_content()
            except:
                # خطة بديلة: نأخذ الاسم من عنوان الصفحة نفسها (Tab Title)
                page_title = page.title() # عادة يكون: "الاسم - Google Maps"
                name = page_title.replace("- Google Maps", "").strip()

            data = {'name': name}
            
            # التصنيف (بنفس منطق المرونة)
            try:
                cat_btn = page.locator("button[jsaction*='category']").first
                if cat_btn.count() > 0:
                    data['category'] = cat_btn.text_content()
                else:
                    data['category'] = "غير محدد"
            except:
                data['category'] = "غير محدد"

            # المراجعات
            data['reviews'] = ""
            try:
                # محاولة الضغط بـ Javascript Force Click
                page.evaluate("document.querySelector('button[aria-label*=\"Reviews\"]').click()") 
                time.sleep(2)
                reviews = page.locator(".wiI7pd").all_text_contents()
                data['reviews'] = " ".join(reviews)
            except: 
                pass

            # الكود الخام
            data['raw_html'] = page.content()
            
            return data
        except Exception as e:
            st.error(f"خطأ تقني: {e}")
            return None
        finally:
            browser.close()

def inspector_analysis(api_key, data):
    genai.configure(api_key=api_key)
    
    # محاولة استخراج التصنيفات المخفية
    hidden_cats_text = "لا توجد"
    try:
        clean_cat = re.escape(data.get('category', ''))
        match = re.search(rf'\[\\"{clean_cat}\\"(.*?)]', data['raw_html'])
        if match:
            extracted = re.findall(r'\\"(.*?)\\"', match.group(1))
            hidden_cats_list = [c for c in extracted if len(c)>2 and not c.isdigit()]
            hidden_cats_text = ", ".join(list(set(hidden_cats_list)))
    except: pass

    model = genai.GenerativeModel('gemini-1.5-flash')
    
    prompt = f"""
    بيانات المنافس ({data['name']}):
    - التصنيف: {data['category']}
    - تصنيفات مخفية محتملة: {hidden_cats_text}
    - مراجعات العملاء: {data['reviews'][:3000]}
    
    المطلوب تحليل SWOT دقيق (نقاط القوة، الضعف، الفرص):
    1. لماذا هذا المنافس قوي؟ (استنتج من المراجعات).
    2. ما هي نقاط ضعفه التي يشتكي منها الناس؟
    3. ما هي الخدمات التي يبيعها بكثرة؟
    4. هل تصنيفاته صحيحة أم يحتاج تعديل؟
    """
    
    try:
        return model.generate_content(prompt).text
    except Exception as e:
        return f"خطأ AI: {e}"

# --- واجهة التشغيل ---
if st.button("🚀 ابدأ الفحص") and raw_url and gemini_key:
    with st.spinner("جاري الاختراق القانوني للبيانات..."):
        result = get_data_deep(raw_url)
        
        if result:
            st.success(f"تم الوصول: {result['name']}")
            
            col1, col2 = st.columns(2)
            col1.metric("التصنيف", result['category'])
            col2.caption(f"تم سحب {len(result['reviews'])} حرف من المراجعات")
            
            st.divider()
            with st.spinner("جاري التحليل..."):
                report = inspector_analysis(gemini_key, result)
                st.markdown(report)
