import streamlit as st
from playwright.sync_api import sync_playwright
import google.generativeai as genai
import time
import re
import os
import subprocess

# --- إعداد الصفحة ---
st.set_page_config(page_title="كاشف المنافسين - GMap Spy", page_icon="🕵️‍♂️", layout="centered")

# --- دالة التثبيت التلقائي (تعمل مرة واحدة فقط) ---
@st.cache_resource
def install_playwright_browser():
    """
    تقوم هذه الدالة بتثبيت متصفح Chromium داخل السيرفر
    لحل مشكلة (Executable doesn't exist)
    """
    print("🛠️ جاري التحقق من متصفح Chromium...")
    try:
        # أمر التثبيت
        subprocess.run(["playwright", "install", "chromium"], check=True)
        print("✅ تم تثبيت المتصفح بنجاح!")
    except Exception as e:
        print(f"⚠️ تنبيه: حدثت مشكلة أثناء محاولة التثبيت: {e}")

# استدعاء الدالة فور تشغيل التطبيق
install_playwright_browser()

# --- واجهة التطبيق ---
st.title("🕵️‍♂️ أداة تحليل المنافسين الذكية")
st.caption("Developed for Local SEO Analysis")

with st.sidebar:
    st.header("⚙️ الإعدادات")
    gemini_key = st.text_input("مفتاح Gemini API", type="password", help="من Google AI Studio")
    st.info("ملاحظة: هذه الأداة تتطلب وقتاً (30-60 ثانية) للسحب من جوجل ماب.")

target_url = st.text_input("🔗 ضع رابط جوجل ماب للمنافس هنا:")
analyze_btn = st.button("🚀 ابدأ التحليل")

# --- الدوال البرمجية (Core Functions) ---

def get_gmap_data(url):
    """سحب البيانات باستخدام Playwright مع تخطي الحماية"""
    data = {}
    
    with sync_playwright() as p:
        # إعدادات المتصفح الخاصة بالسيرفرات (مهمة جداً)
        browser = p.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu'
            ]
        )
        
        # إنشاء سياق متصفح جديد
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        )
        page = context.new_page()

        try:
            # زيادة وقت الانتظار لـ 60 ثانية
            page.goto(url, timeout=60000)
            
            # انتظار ذكي حتى تحميل العناصر الأساسية
            page.wait_for_selector("h1", timeout=30000)
            
            # 1. سحب الاسم
            data['name'] = page.locator("h1").inner_text()
            
            # 2. سحب التصنيف الأساسي
            try:
                data['category'] = page.locator("button[jsaction*='category']").first.inner_text()
            except:
                data['category'] = "غير محدد"

            # 3. سحب المراجعات (تحتاج ضغط زر)
            try:
                reviews_btn = page.locator("button[aria-label*='Reviews'], button[aria-label*='مراجعات']")
                if reviews_btn.count() > 0:
                    reviews_btn.first.click()
                    time.sleep(4) # انتظار فتح القائمة
                    
                    # محاولة سكرول بسيطة
                    page.mouse.wheel(0, 2000)
                    time.sleep(1)
                    
                    reviews = page.locator(".wiI7pd").all_inner_texts()
                    data['reviews'] = " ".join(reviews)
                else:
                    data['reviews'] = ""
            except:
                data['reviews'] = "لم يتم سحب مراجعات"

            # 4. سحب الكود للتصنيفات المخفية
            data['html_source'] = page.content()
            
        except Exception as e:
            st.error(f"حدث خطأ أثناء الاتصال بجوجل: {e}")
            return None
        finally:
            browser.close()
            
    return data

def extract_hidden_cats(html, primary_cat):
    """استخراج التصنيفات المخفية باستخدام Regex"""
    if not html or not primary_cat:
        return []
    
    # تنظيف النص للبحث
    clean_primary = re.escape(primary_cat)
    # البحث عن النمط الذي تستخدمه جوجل: ["Primary", "Hidden1", "Hidden2"]
    pattern = rf'\[\\"{clean_primary}\\"(.*?)]'
    
    matches = re.search(pattern, html)
    if matches:
        raw = matches.group(1)
        cats = re.findall(r'\\"(.*?)\\"', raw)
        # فلترة: حذف الكلمات القصيرة جداً والأرقام
        return list(set([c for c in cats if len(c) > 2 and not c.isdigit()]))
    return []

def analyze_with_gemini(api_key, business_data, hidden_cats):
    """إرسال البيانات لـ Gemini للتحليل"""
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-pro')
    
    # تحضير النص (Prompt)
    reviews_snippet = business_data.get('reviews', '')[:3000] # تقليص النص لتجنب تجاوز الحد
    
    prompt = f"""
    أنت خبير SEO محلي (Local SEO) متخصص في Google Business Profile.
    قم بتحليل بيانات هذا المنافس بدقة:
    
    اسم النشاط: {business_data.get('name')}
    التصنيف الأساسي: {business_data.get('category')}
    التصنيفات الثانوية المكتشفة: {', '.join(hidden_cats)}
    عينة من آراء العملاء: {reviews_snippet}
    
    المطلوب منك (باللغة العربية):
    1. استخرج أهم 5 كلمات مفتاحية (Keywords) تكررت في المراجعات الإيجابية.
    2. حدد نقطة ضعف واحدة أو شكوى تكررت عند العملاء (لنستغلها).
    3. اقترح علي 3 تصنيفات (Categories) يجب أن أضيفها لملفي فوراً.
    4. اكتب "وصف نشاط" (Business Description) احترافي وجذاب يتضمن الكلمات المفتاحية المستخرجة.
    """
    
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"خطأ في الاتصال بـ Gemini: {e}"

# --- منطق التشغيل ---

if analyze_btn:
    if not gemini_key or not target_url:
        st.warning("⚠️ يرجى التأكد من إدخال مفتاح API ورابط المنافس.")
    else:
        with st.spinner('🕵️‍♂️ جاري الاتصال بالقمر الصناعي وسحب البيانات...'):
            # 1. السحب
            result = get_gmap_data(target_url)
            
            if result:
                st.success(f"تم سحب البيانات لـ: {result.get('name')}")
                
                # 2. استخراج المخفي
                hidden = extract_hidden_cats(result.get('html_source'), result.get('category'))
                
                # عرض النتائج الأولية
                col1, col2 = st.columns(2)
                col1.metric("التصنيف الأساسي", result.get('category'))
                col2.metric("عدد المراجعات المسحوبة", len(result.get('reviews', '')) // 50) # تقديري
                
                if hidden:
                    with st.expander("🔥 التصنيفات المخفية (Secondary Categories)"):
                        st.write(hidden)
                
                # 3. تحليل الذكاء الاصطناعي
                st.markdown("---")
                st.subheader("🧠 تقرير الذكاء الاصطناعي")
                with st.spinner("جاري الكتابة..."):
                    ai_report = analyze_with_gemini(gemini_key, result, hidden)
                    st.markdown(ai_report)
