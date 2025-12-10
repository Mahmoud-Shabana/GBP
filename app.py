import streamlit as st
from playwright.sync_api import sync_playwright
import google.generativeai as genai
import time
import re

# 1. إعداد واجهة الموقع
st.set_page_config(page_title="كاشف المنافسين - Google Maps Spy", page_icon="🕵️‍♂️", layout="centered")

st.title("🕵️‍♂️ أداة تحليل المنافسين الذكية")
st.caption("باستخدام Python + Gemini AI")

# 2. المدخلات من المستخدم
with st.sidebar:
    st.header("الإعدادات")
    gemini_key = st.text_input("مفتاح Gemini API", type="password", help="احصل عليه مجاناً من Google AI Studio")
    st.info("هذه الأداة للاستخدام الشخصي التعليمي.")

target_url = st.text_input("ضع رابط جوجل ماب للمنافس هنا:")
analyze_btn = st.button("🚀 ابدأ التحليل وكشف الأسرار")

# --- دوال البرنامج ---

def get_gmap_data(url):
    """وظيفة الجاسوس: تدخل الصفحة وتسحب البيانات الظاهرة والمخفية"""
    data = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto(url, timeout=60000)
            page.wait_for_load_state("networkidle")
            
            # سحب الاسم
            data['name'] = page.locator("h1").inner_text()
            
            # سحب التصنيف الأساسي
            try:
                data['category'] = page.locator("button[jsaction*='category']").first.inner_text()
            except:
                data['category'] = "غير محدد"

            # سحب المراجعات
            try:
                page.locator("button[aria-label*='Reviews']").click()
                time.sleep(2)
                # سكرول بسيط لتحميل المزيد
                for _ in range(3):
                    page.mouse.wheel(0, 2000)
                    time.sleep(1)
                reviews = page.locator(".wiI7pd").all_inner_texts()
                data['reviews'] = " ".join(reviews)
            except:
                data['reviews'] = "لا توجد مراجعات نصية."

            # محاولة سحب الـ Source Code للبحث عن التصنيفات المخفية
            data['html_source'] = page.content()
            
        except Exception as e:
            st.error(f"حدث خطأ أثناء السحب: {e}")
        
        browser.close()
    return data

def extract_hidden_cats(html, primary_cat):
    """وظيفة البحث الجراحي في الكود"""
    clean_primary = re.escape(primary_cat)
    # باترن يبحث عن التصنيفات المجاورة
    pattern = rf'\[\\"{clean_primary}\\"(.*?)]'
    matches = re.search(pattern, html)
    if matches:
        raw = matches.group(1)
        cats = re.findall(r'\\"(.*?)\\"', raw)
        return list(set([c for c in cats if len(c) > 2 and not c.isdigit()]))
    return []

def analyze_with_gemini(api_key, business_data, hidden_cats):
    """وظيفة المحلل الذكي: يرسل البيانات لجيمناي ويعود بالخطة"""
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-pro')
    
    prompt = f"""
    أنت خبير SEO متخصص في خرائط جوجل (Google Business Profile).
    لدينا بيانات لمنافس قوي، أريدك أن تحللها وتعطيني خطة للتفوق عليه.
    
    بيانات المنافس:
    - الاسم: {business_data.get('name')}
    - التصنيف الأساسي: {business_data.get('category')}
    - التصنيفات الثانوية (المخفية): {', '.join(hidden_cats)}
    - آراء العملاء (نص خام): {business_data.get('reviews')[:4000]} (تم قص النص للطول)

    المطلوب منك في تقريرك:
    1. استخرج أهم 5 كلمات مفتاحية (Keywords) تكررت في كلام العملاء بمدح، لنستخدمها في وصفنا.
    2. ما هي "نقاط الألم" (Pain Points) التي اشتكى منها العملاء (إن وجدت) لنتميز نحن فيها؟
    3. اقترح علي 3 تصنيفات (Categories) يجب أن أضيفها في ملفي بناء على ما يفعله هذا المنافس.
    4. اكتب لي "وصف نشاط" (Description) احترافي ومحسن بالـ SEO لشركتي (افترض أني أقدم نفس الخدمة) مستخدماً الكلمات المكتشفة.
    
    اجعل الرد باللغة العربية ومنسقاً بشكل جذاب.
    """
    
    response = model.generate_content(prompt)
    return response.text

# --- التنفيذ ---

if analyze_btn and target_url and gemini_key:
    with st.spinner('🕵️‍♂️ جاري إرسال الجاسوس... (قد تستغرق العملية دقيقة)'):
        # 1. سحب البيانات
        biz_data = get_gmap_data(target_url)
        
        if biz_data:
            st.success(f"تم الوصول إلى: {biz_data.get('name')}")
            
            # 2. استخراج المخفي
            hidden_categories = extract_hidden_cats(biz_data.get('html_source'), biz_data.get('category'))
            
            st.write("---")
            col1, col2 = st.columns(2)
            with col1:
                st.metric("التصنيف الأساسي", biz_data.get('category'))
            with col2:
                st.metric("عدد المراجعات المحللة", len(biz_data.get('reviews')) // 50) # تقديري

            if hidden_categories:
                with st.expander("👁️ عرض التصنيفات المخفية (Secondary Categories)"):
                    st.write(hidden_categories)
            
            # 3. التحليل بالذكاء الاصطناعي
            st.write("---")
            st.subheader("🧠 تحليل الذكاء الاصطناعي (Gemini Analysis)")
            with st.spinner("جاري كتابة الخطة الاستراتيجية..."):
                try:
                    analysis = analyze_with_gemini(gemini_key, biz_data, hidden_categories)
                    st.markdown(analysis)
                except Exception as e:
                    st.error(f"خطأ في مفتاح Gemini أو الاتصال: {e}")