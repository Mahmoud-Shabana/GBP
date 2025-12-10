import streamlit as st
from playwright.sync_api import sync_playwright
import google.generativeai as genai
import time
import re
import os
import subprocess

# --- 1. إعداد الصفحة وتجهيز البيئة ---
st.set_page_config(page_title="كاشف المنافسين - GMap Spy", page_icon="🕵️‍♂️", layout="wide")

# تثبيت المتصفح تلقائياً عند التشغيل لأول مرة
@st.cache_resource
def install_environment():
    """تجهيز بيئة التشغيل وتثبيت المتصفح"""
    print("🛠️ جاري فحص وتثبيت متصفح Chromium...")
    try:
        subprocess.run(["playwright", "install", "chromium"], check=True)
        print("✅ تم التثبيت بنجاح.")
    except Exception as e:
        print(f"⚠️ تنبيه: {e}")

install_environment()

# --- 2. دوال مساعدة (تحسينات) ---

def clean_gmap_url(url):
    """تنظيف الرابط من البيانات الزائدة التي تسبب أخطاء"""
    if not url: return ""
    # إذا كان الرابط طويلاً ويحتوي على !data، نحذفه
    if "!3m" in url or "!4m" in url:
        # نحاول الاحتفاظ بالجزء الأساسي فقط
        match = re.search(r'(https?://.*?/maps/place/[^/]+/@[\d\.\,\-]+z)', url)
        if match:
            return match.group(1)
    return url

def get_gmap_data(url):
    """سحب البيانات بمتصفح خفي مع تمويه (Anti-Detection)"""
    data = {}
    
    with sync_playwright() as p:
        # إعدادات لتفادي كشف الروبوت ولمنع الانهيار
        browser = p.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-blink-features=AutomationControlled' # تمويه إضافي
            ]
        )
        
        # استخدام User-Agent لجهاز ويندوز طبيعي
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        try:
            # استخدام الرابط النظيف
            clean_link = clean_gmap_url(url)
            page.goto(clean_link if clean_link else url, timeout=60000)
            
            # انتظار ظهور اسم المكان
            try:
                page.wait_for_selector("h1", timeout=20000)
            except:
                pass # نكمل حتى لو تأخر قليلاً

            # 1. سحب الاسم
            try:
                data['name'] = page.locator("h1").inner_text()
            except:
                data['name'] = "غير معروف"
            
            # 2. سحب التصنيف
            try:
                data['category'] = page.locator("button[jsaction*='category']").first.inner_text()
            except:
                data['category'] = "غير محدد"

            # 3. سحب المراجعات
            data['reviews'] = ""
            try:
                # البحث عن زر المراجعات بعدة صيغ
                reviews_btn = page.locator("button[aria-label*='Reviews'], button[aria-label*='مراجعات'], div[role='tablist'] button:has-text('Reviews')")
                
                if reviews_btn.count() > 0:
                    reviews_btn.first.click()
                    time.sleep(3)
                    
                    # سكرول لتحميل المزيد
                    for _ in range(3):
                        page.mouse.wheel(0, 3000)
                        time.sleep(1)
                    
                    reviews = page.locator(".wiI7pd").all_inner_texts()
                    data['reviews'] = " ".join(reviews)
                    data['reviews_count'] = len(reviews)
                else:
                    data['reviews_count'] = 0
            except:
                data['reviews'] = "تعذر سحب النصوص"

            # 4. سحب الكود للتصنيفات المخفية
            data['html_source'] = page.content()
            
        except Exception as e:
            st.error(f"خطأ المتصفح: {e}")
            return None
        finally:
            browser.close()
            
    return data

def extract_hidden_cats(html, primary_cat):
    """استخراج التصنيفات الثانوية من الكود"""
    if not html or not primary_cat: return []
    clean_primary = re.escape(primary_cat)
    pattern = rf'\[\\"{clean_primary}\\"(.*?)]'
    matches = re.search(pattern, html)
    if matches:
        raw = matches.group(1)
        cats = re.findall(r'\\"(.*?)\\"', raw)
        return list(set([c for c in cats if len(c) > 2 and not c.isdigit()]))
    return []

def analyze_with_gemini(api_key, biz_data, hidden_cats):
    """التحليل باستخدام الموديل الجديد Flash"""
    try:
        genai.configure(api_key=api_key)
        # استخدام الموديل الأحدث
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        reviews_text = biz_data.get('reviews', '')
        if not reviews_text:
            reviews_text = "لا توجد مراجعات نصية، اعتمد على الاسم والتصنيف."

        prompt = f"""
        دورك: خبير SEO واستراتيجيات Google Maps.
        
        المعطيات عن المنافس:
        - الاسم: {biz_data.get('name')}
        - التصنيف الأساسي: {biz_data.get('category')}
        - التصنيفات المخفية: {', '.join(hidden_cats)}
        - عينة من كلام العملاء: {reviews_text[:4000]}
        
        المطلوب تقرير عملي (Action Plan):
        1. **الكلمات المفتاحية الذهبية:** استخرج 5 كلمات يبحث عنها الناس لهذا النشاط.
        2. **كشف الأسرار:** ماذا يفعل هذا المنافس بشكل صحيح؟ (بناءً على التصنيفات والمراجعات).
        3. **الثغرات:** ما هي الفرصة الضائعة التي يمكننا استغلالها؟
        4. **خطة المحتوى:** اقترح عنوانين لمنشورات (Posts) وصورة يجب أن أرفعها لملفي.
        5. **الوصف المقترح:** اكتب وصفاً (Description) لشركتي يتضمن الكلمات المفتاحية.
        
        نسق الإجابة بعناوين واضحة ورموز تعبيرية.
        """
        
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"خطأ API: {e}"

# --- 3. واجهة المستخدم ---

st.title("🕵️‍♂️ Spy Maps Pro")
st.markdown("تحليل المنافسين وكشف استراتيجيات الـ SEO الخاصة بهم.")

with st.sidebar:
    st.header("🔐 بيانات الدخول")
    gemini_key = st.text_input("Gemini API Key", type="password")
    st.markdown("---")
    st.info("نصيحة: استخدم الرابط الطويل من المتصفح للحصول على أفضل نتيجة.")

url_input = st.text_input("رابط المنافس (Google Maps Link):", placeholder="https://www.google.com/maps/place/...")
btn = st.button("🚀 تحليل الآن", type="primary")

if btn:
    if not gemini_key or not url_input:
        st.warning("تأكد من إدخال الرابط ومفتاح الـ API.")
    else:
        with st.status("جاري العمل...", expanded=True) as status:
            st.write("📡 الاتصال بجوجل ماب...")
            result = get_gmap_data(url_input)
            
            if result:
                st.write("✅ تم سحب البيانات الأساسية.")
                hidden = extract_hidden_cats(result.get('html_source'), result.get('category'))
                
                status.update(label="اكتمل السحب! جاري التحليل بالذكاء الاصطناعي...", state="running")
                report = analyze_with_gemini(gemini_key, result, hidden)
                
                status.update(label="تمت المهمة بنجاح!", state="complete", expanded=False)
                
                # --- عرض النتائج ---
                st.divider()
                
                # قسم المعلومات العلوية
                col1, col2, col3 = st.columns(3)
                col1.metric("الاسم", result.get('name'))
                col2.metric("التصنيف الأساسي", result.get('category'))
                col3.metric("عدد المراجعات المسحوبة", result.get('reviews_count', 0))
                
                # قسم التصنيفات المخفية
                if hidden:
                    st.success(f"🎯 التصنيفات المخفية المكتشفة: {', '.join(hidden)}")
                else:
                    st.info("لم يتم العثور على تصنيفات ثانوية مخفية.")
                
                # التقرير الذكي
                st.subheader("🧠 التقرير الاستراتيجي")
                st.markdown(report)
                
            else:
                status.update(label="فشلت العملية", state="error")
                st.error("لم نتمكن من الوصول للرابط. تأكد أنه رابط صحيح (طويل) وحاول مرة أخرى.")
