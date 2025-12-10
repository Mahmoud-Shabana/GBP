import streamlit as st
from playwright.sync_api import sync_playwright
import google.generativeai as genai
import time
import re
import os
import subprocess

st.set_page_config(page_title="GMap Spy (Debug)", page_icon="🕵️‍♂️", layout="centered")

@st.cache_resource
def setup():
    # تثبيت المتصفح بصمت
    if not os.path.exists("packages.txt"):
        subprocess.run(["playwright", "install", "chromium"], check=False)

setup()

st.title("🕵️‍♂️ كاشف المنافسين (وضع التشخيص)")
st.warning("هذه النسخة ستقوم بتصوير الشاشة إذا حدث خطأ لنعرف السبب.")

with st.sidebar:
    gemini_key = st.text_input("Gemini API Key", type="password")

url = st.text_input("رابط جوجل ماب:")
btn = st.button("تحليل")

def get_data(target_url):
    with sync_playwright() as p:
        # 1. إعدادات تخفي قصوى
        browser = p.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-blink-features=AutomationControlled',
                '--window-size=1920,1080', # حجم شاشة كبير لتجنب وضع الموبايل
                '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            ]
        )
        page = browser.new_page()
        
        try:
            st.info("جاري الاتصال...")
            
            # تنظيف الرابط
            if "/data=" in target_url:
                target_url = target_url.split("/data=")[0]
            
            page.goto(target_url, timeout=60000, wait_until='domcontentloaded')
            
            # 2. محاولة التعامل مع نوافذ الكوكيز (Consent Cookies)
            # جوجل أحياناً يظهر زر "Accept all" يغطي الشاشة
            try:
                page.locator("button:has-text('Accept all')").click(timeout=3000)
                time.sleep(2)
            except:
                pass

            # 3. الانتظار والتحقق
            try:
                page.wait_for_selector("h1", state="visible", timeout=15000)
            except:
                # 📸 أهم خطوة: تصوير الشاشة عند الفشل
                st.error("فشل العثور على العنصر. هذه صورة لما يراه الروبوت الآن:")
                screenshot = page.screenshot()
                st.image(screenshot, caption="لقطة شاشة من السيرفر", use_column_width=True)
                return None

            # سحب البيانات
            name = page.locator("h1").first.inner_text()
            
            # سحب التصنيف
            try:
                cat = page.locator("button[jsaction*='category']").first.inner_text()
            except:
                cat = "غير محدد"
                
            # سحب المراجعات
            reviews = ""
            try:
                page.locator("button[aria-label*='Reviews'], button[aria-label*='مراجعات']").first.click()
                time.sleep(2)
                reviews = " ".join(page.locator(".wiI7pd").all_inner_texts())
            except:
                pass

            # سحب الكود للمخفي
            html = page.content()
            
            return {"name": name, "cat": cat, "reviews": reviews, "html": html}

        except Exception as e:
            st.error(f"خطأ غير متوقع: {e}")
            return None
        finally:
            browser.close()

def extract_hidden(html, primary):
    if not html or not primary: return []
    clean = re.escape(primary)
    try:
        m = re.search(rf'\[\\"{clean}\\"(.*?)]', html)
        if m:
            return list(set([c for c in re.findall(r'\\"(.*?)\\"', m.group(1)) if len(c)>2 and not c.isdigit()]))
    except:
        pass
    return []

def analyze_ai(api_key, data, hidden):
    genai.configure(api_key=api_key)
    # استخدام قائمة موديلات احتياطية
    for m in ['gemini-1.5-flash', 'gemini-pro']:
        try:
            model = genai.GenerativeModel(m)
            prompt = f"حلل: {data['name']} - {data['cat']} - {hidden} - {data['reviews'][:1000]}"
            return model.generate_content(prompt).text
        except:
            continue
    return "فشل الاتصال بـ Gemini"

if btn and url and gemini_key:
    data = get_data(url)
    if data:
        st.success(f"تم الوصول: {data['name']}")
        hidden = extract_hidden(data['html'], data['cat'])
        st.write(f"التصنيفات: {data['cat']} | {hidden}")
        st.write(analyze_ai(gemini_key, data, hidden))
