import streamlit as st
from playwright.sync_api import sync_playwright
import google.generativeai as genai
import time
import re
import os
import subprocess

# --- 1. إعداد الصفحة وتثبيت المتصفح (مهم جداً للاستضافة) ---
st.set_page_config(page_title="كاشف المنافسين - GMap Spy", page_icon="🕵️‍♂️", layout="centered")

@st.cache_resource
def install_playwright_browser():
    """
    هذه الدالة تعمل مرة واحدة فقط عند تشغيل السيرفر
    لضمان تثبيت متصفح Chromium المطلوب
    """
    print("🛠️ جاري تثبيت متصفح Chromium...")
    try:
        subprocess.run(["playwright", "install", "chromium"], check=True)
        print("✅ تم التثبيت بنجاح!")
    except Exception as e:
        print(f"❌ حدث خطأ أثناء التثبيت: {e}")

# استدعاء دالة التثبيت
install_playwright_browser()

st.title("🕵️‍♂️ أداة تحليل المنافسين الذكية")
st.caption("باستخدام Python + Gemini AI")

# --- 2. واجهة المستخدم ---
with st.sidebar:
    st.header("الإعدادات")
    gemini_key = st.text_input("مفتاح Gemini API", type="password", help="احصل عليه من Google AI Studio")
    st.info("هذه الأداة مخصصة للاستخدام الشخصي التعليمي.")

target_url = st.text_input("ضع رابط جوجل ماب للمنافس هنا:")
analyze_btn = st.button("🚀 ابدأ التحليل")

# --- 3. الوظائف البرمجية (Core Functions) ---

def get_gmap_data(url):
    """وظيفة الجاسوس: تدخل الصفحة وتسحب البيانات"""
    data = {}
    
    with sync_playwright() as p:
        # التعديل الهام جداً لمنع الانهيار على السيرفر
        browser = p.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu'
            ]
        )
        
        page = browser.new_page()
        try:
            # زيادة وقت الانتظار لضمان التحميل على السيرفرات البطيئة
            page.goto(url, timeout=90000)
            page.wait_for_load_state("networkidle")
            
            # سحب الاسم
            try:
                data['name'] = page.locator("h1").inner_text()
            except:
                data['name'] = "غير معروف"
            
            # سحب التصنيف الأساسي
            try:
                data['category'] = page.locator("button[jsaction*='category']").first.inner_text()
            except:
                data['category'] = "غير محدد"

            # سحب المراجعات
            try:
                # محاولة الضغط على زر المراجعات
                reviews_btn = page.locator("button[aria-label*='Reviews'], button[aria-label*='مراجعات']")
                if reviews_btn.count() > 0:
                    reviews_btn.first.click()
                    time.sleep(3)
                    
                    # سكرول بسيط
                    for _ in range(3):
                        page.mouse.wheel(0, 3000)
                        time.sleep(1)
                        
                    reviews = page.locator(".wiI7pd").all_inner_texts()
                    data['reviews'] = " ".join(reviews)
                else:
                    data['reviews'] = ""
            except Exception as e:
                print(f"Review Error: {e}")
                data['reviews'] = "لا توجد مراجعات نصية."

            # سحب الكود المصدري للتصنيفات المخفية
            data['html_source'] = page.content()
            
        except Exception as e:
            st.error(f"حدث خطأ أثناء السحب: {e}")
            # إرجاع بيانات فارغة لتجنب توقف البرنامج
            return None
        finally:
            browser.close()
            
    return data

def extract_hidden_cats(html, primary_cat):
    """استخراج التصنيفات المخفية من الكود"""
    if not html or not primary_cat:
        return []
        
    clean_primary = re.escape(primary_cat)
    # البحث عن النمط ["Category", "Hidden 1", "Hidden 2"]
    pattern = rf'\[\\"{clean_primary}\\"(.*?)]'
    matches = re.search(pattern, html)
    
    if matches:
        raw = matches.group(1)
        cats = re.findall(r'\\"(.*?)\\"', raw)
        # فلترة النتائج
        return list(set([c for c in cats if len(c) > 2 and not c.isdigit()]))
    return []

def analyze_with_gemini(api_key, business_data, hidden_cats):
    """التحليل بالذكاء الاصطناعي"""
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-pro')
    
    reviews_text = business_data.get('reviews', '')[:4000] # تقليص النص لحدود الـ Token
    
    prompt = f"""
    تصرف كخبير SEO محترف في خرائط جوجل. قم بتحليل بيانات هذا المنافس:
    
    - الاسم: {business_data.get('name')}
    - التصنيف الأساسي: {business_data.get('category')}
    - التصنيفات المخفية: {', '.join(hidden_cats)}
    - آراء العملاء: {reviews_text}

    المطلوب تقرير استراتيجي مفصل:
    1. أهم 5 كلمات مفتاحية (Keywords) تكررت في المراجعات الإيجابية.
    2. أبرز نقاط الضعف أو الشكاوى عند المنافس (لنستغلها).
    3. اقترح 3 تصنيفات إضافية يجب أن أضيفها لملفي.
    4. اكتب وصفاً (Description) احترافياً وجذاباً لنشاطي مشابهاً لهذا المنافس ولكن أفضل منه.
    
    اجعل الإجابة باللغة العربية ومنسقة بشكل جميل.
    """
    
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"حدث خطأ في الاتصال بـ Gemini: {e}"

# --- 4. منطق التشغيل الرئيسي ---

if analyze_btn:
    if not gemini_key:
        st.warning("⚠️ يرجى إدخال مفتاح Gemini API أولاً.")
    elif not target_url:
        st.warning("⚠️ يرجى وضع رابط المنافس.")
    else:
        with st.spinner('🕵️‍♂️ جاري الاتصال بالقمر الصناعي... وسحب البيانات...'):
            # 1. سحب البيانات
            biz_data = get_gmap_data(target_url)
            
            if biz_data:
                st.success(f"تم الوصول للهدف: {biz_data.get('name')}")
                
                # 2. استخراج المخفي
                hidden_categories = extract_hidden_cats(biz_data.get('html_source'), biz_data.get('category'))
                
                # عرض البيانات الأساسية
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("التصنيف الأساسي", biz_data.get('category'))
                with col2:
                    st.metric("طول المراجعات", len(biz_data.get('reviews', '')))

                if hidden_categories:
                    with st.expander("👁️ التصنيفات الثانوية المكتشفة (SEO Gold)"):
                        for cat in hidden_categories:
                            st.write(f"- {cat}")
                
                # 3. تحليل Gemini
                st.divider()
                st.subheader("🧠 تقرير الذكاء الاصطناعي")
                
                with st.spinner("جاري كتابة الخطة الاستراتيجية..."):
                    analysis_result = analyze_with_gemini(gemini_key, biz_data, hidden_categories)
                    st.markdown(analysis_result)
            else:
                st.error("فشلت عملية السحب. تأكد أن الرابط صحيح أو حاول مرة أخرى.")
