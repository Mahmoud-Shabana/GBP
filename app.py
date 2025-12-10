import streamlit as st
from playwright.sync_api import sync_playwright
import google.generativeai as genai
import time
import re
import os
import subprocess

# --- 1. إعداد الصفحة ---
st.set_page_config(page_title="GMap Spy", page_icon="🕵️‍♂️", layout="centered")

@st.cache_resource
def setup_environment():
    """تجهيز البيئة وتثبيت المتصفح"""
    try:
        subprocess.run(["playwright", "install", "chromium"], check=True)
    except:
        pass

setup_environment()

# --- 2. واجهة المستخدم ---
st.title("🕵️‍♂️ Spy Maps Pro")
st.caption("أداة تحليل المنافسين (الإصدار المحسن)")

with st.sidebar:
    gemini_key = st.text_input("Gemini API Key", type="password")
    
target_url = st.text_input("🔗 رابط المنافس:")
analyze_btn = st.button("🚀 تحليل")

# --- 3. الدوال (Scraping & AI) ---

def clean_url(url):
    """تنظيف الرابط لضمان الفتح الصحيح"""
    # نحاول استخراج الرابط النظيف لو كان معقداً
    if "maps/place" in url:
        return url.split("/data=")[0]
    return url

def get_gmap_data(url):
    """سحب البيانات مع انتظار ذكي للعناصر"""
    data = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-gpu']
        )
        page = browser.new_page(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        try:
            final_url = clean_url(url)
            page.goto(final_url, timeout=60000)
            
            # الانتظار حتى يظهر الاسم (أهم خطوة)
            try:
                page.wait_for_selector("h1", timeout=20000)
            except:
                st.error("⚠️ لم نتمكن من العثور على اسم المكان. قد يكون الرابط خاطئاً أو أن جوجل حظر المحاولة.")
                return None

            # 1. سحب الاسم
            data['name'] = page.locator("h1").first.inner_text()
            
            # 2. سحب التصنيف (محاولة بعدة طرق)
            try:
                # طريقة 1: الزر المعتاد
                data['category'] = page.locator("button[jsaction*='category']").first.inner_text()
            except:
                try:
                    # طريقة 2: البحث عن أي نص رمادي تحت الاسم
                    data['category'] = page.locator("h1 + div span").first.inner_text()
                except:
                    data['category'] = "تصنيف غير محدد"

            # 3. سحب المراجعات
            try:
                # الضغط على تبويب المراجعات
                page.locator("button[aria-label*='Reviews'], button[aria-label*='مراجعات']").first.click()
                time.sleep(2)
                data['reviews'] = " ".join(page.locator(".wiI7pd").all_inner_texts())
            except:
                data['reviews'] = ""

            # 4. الكود المصدري للمخفي
            data['html_source'] = page.content()
            
        except Exception as e:
            st.error(f"حدث خطأ فني أثناء السحب: {e}")
            return None
        finally:
            browser.close()
            
    return data

def extract_hidden(html, primary):
    if not html or not primary: return []
    clean = re.escape(primary)
    try:
        match = re.search(rf'\[\\"{clean}\\"(.*?)]', html)
        if match:
            return list(set([c for c in re.findall(r'\\"(.*?)\\"', match.group(1)) if len(c)>2 and not c.isdigit()]))
    except:
        pass
    return []

def get_ai_advice(api_key, data, hidden):
    genai.configure(api_key=api_key)
    
    # محاولة استخدام الفلاش أولاً، ثم العادي
    models_to_try = ['gemini-1.5-flash', 'gemini-pro']
    
    prompt = f"""
    حلل هذا النشاط التجاري:
    الاسم: {data.get('name')}
    التصنيف: {data.get('category')}
    التصنيفات المخفية: {hidden}
    مراجعات: {data.get('reviews')[:1000]}
    
    المطلوب:
    1. كلمات مفتاحية مقترحة.
    2. نصائح لتحسين الظهور.
    3. وصف احترافي للنشاط.
    """
    
    for model_name in models_to_try:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            return response.text
        except Exception:
            continue # جرب الموديل اللي بعده
            
    return "فشل الاتصال بجميع موديلات Gemini. تأكد من المفتاح وصلاحية الحساب."

# --- التشغيل ---
if analyze_btn and gemini_key and target_url:
    with st.spinner("جاري العمل..."):
        result = get_gmap_data(target_url)
        if result:
            st.success(f"تم! {result['name']}")
            hidden_cats = extract_hidden(result.get('html_source'), result.get('category'))
            
            col1, col2 = st.columns(2)
            col1.metric("التصنيف", result.get('category'))
            if hidden_cats:
                col2.write(f"المخفي: {hidden_cats}")
                
            st.markdown("---")
            st.markdown(get_ai_advice(gemini_key, result, hidden_cats))
