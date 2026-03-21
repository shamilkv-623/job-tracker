import streamlit as st
import pandas as pd
import sqlite3
import bcrypt
import time
from io import BytesIO
from scraper_engine import generic_scraper
from utils import extract_text_from_pdf, extract_keywords_from_cv

# --- 1. DATABASE SETUP & HELPERS ---
def init_db():
    conn = sqlite3.connect('job_tracker.db')
    c = conn.cursor()
    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, password TEXT, keywords TEXT)''')
    # URLs table
    c.execute('''CREATE TABLE IF NOT EXISTS urls 
                 (username TEXT, url TEXT, UNIQUE(username, url))''')
    conn.commit()
    conn.close()

def add_user(username, password):
    conn = sqlite3.connect('job_tracker.db')
    c = conn.cursor()
    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    try:
        c.execute("INSERT INTO users (username, password, keywords) VALUES (?, ?, ?)", (username, hashed, ""))
        conn.commit()
        return True
    except: return False
    finally: conn.close()

def check_user(username, password):
    conn = sqlite3.connect('job_tracker.db')
    c = conn.cursor()
    c.execute("SELECT password FROM users WHERE username = ?", (username,))
    result = c.fetchone()
    conn.close()
    if result and bcrypt.checkpw(password.encode('utf-8'), result[0].encode('utf-8')):
        return True
    return False

def get_user_keywords(username):
    conn = sqlite3.connect('job_tracker.db')
    c = conn.cursor()
    c.execute("SELECT keywords FROM users WHERE username = ?", (username,))
    res = c.fetchone()[0]
    conn.close()
    return [k.strip() for k in res.split(",") if k.strip()] if res else []

def save_user_keywords(username, kw_list):
    conn = sqlite3.connect('job_tracker.db')
    c = conn.cursor()
    c.execute("UPDATE users SET keywords = ? WHERE username = ?", (",".join(kw_list), username))
    conn.commit()
    conn.close()

def get_user_urls(username):
    conn = sqlite3.connect('job_tracker.db')
    c = conn.cursor()
    c.execute("SELECT url FROM urls WHERE username = ?", (username,))
    res = [row[0] for row in c.fetchall()]
    conn.close()
    return res

# --- 2. APP CONFIG ---
st.set_page_config(page_title="Horizon AI | Career Monitor", layout="wide", page_icon="🚀")
init_db()

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = ""

# --- 3. LOGIN / SIGNUP UI ---
if not st.session_state.logged_in:
    st.title("🔐 AI Job Tracker Login")
    tab1, tab2 = st.tabs(["Login", "Create Account"])
    
    with tab1:
        u = st.text_input("Username", key="login_u")
        p = st.text_input("Password", type="password", key="login_p")
        if st.button("Login"):
            if check_user(u, p):
                st.session_state.logged_in = True
                st.session_state.username = u
                st.rerun()
            else: st.error("Invalid credentials")
                
    with tab2:
        new_u = st.text_input("Choose Username", key="reg_u")
        new_p = st.text_input("Choose Password", type="password", key="reg_p")
        if st.button("Register"):
            if add_user(new_u, new_p):
                st.success("Account created! You can now login.")
            else: st.error("Username already exists.")
    st.stop()

# --- 4. DASHBOARD ---
username = st.session_state.username
st.sidebar.title(f"👋 Welcome, {username.upper()}")
if st.sidebar.button("Logout"):
    st.session_state.logged_in = False
    st.rerun()

st.title("🚀 Your Job Monitoring Dashboard")

# --- UI: STEP 1 (PROFILE) ---
st.subheader("🎯 Step 1: Your Master Profile")
current_keywords = get_user_keywords(username)
col_k1, col_k2 = st.columns([2, 1])

with col_k1:
    kw_input = st.text_input("Current Search Keywords", value=", ".join(current_keywords))
with col_k2:
    uploaded_file = st.file_uploader("Sync with CV (PDF)", type=["pdf"])

if st.button("💾 Save Profile Settings"):
    updated_kw = [k.strip().lower() for k in kw_input.split(",") if k.strip()]
    if uploaded_file:
        with st.spinner("Extracting insights from PDF..."):
            text = extract_text_from_pdf(uploaded_file)
            updated_kw.extend(extract_keywords_from_cv(text))
    
    # Remove duplicates
    final_kw_list = list(set(updated_kw))
    save_user_keywords(username, final_kw_list)
    st.success("Profile Updated!")
    st.rerun()

st.divider()

# --- UI: STEP 2 (URLS) ---
st.subheader("🌐 Step 2: Your Tracked Companies")
new_url = st.text_input("Add Career Portal URL (e.g., https://jobs.deloitte.com)")
if st.button("➕ Add to My List"):
    if new_url:
        conn = sqlite3.connect('job_tracker.db')
        c = conn.cursor()
        try:
            c.execute("INSERT INTO urls (username, url) VALUES (?, ?)", (username, new_url))
            conn.commit()
            st.rerun()
        except: st.warning("Site is already in your list.")
        finally: conn.close()

# Display URL List
user_urls = get_user_urls(username)
for i, url in enumerate(user_urls):
    c1, c2 = st.columns([9, 1])
    c1.caption(f"📍 {url}")
    if c2.button("🗑️", key=f"del_{i}"):
        conn = sqlite3.connect('job_tracker.db')
        c = conn.cursor()
        c.execute("DELETE FROM urls WHERE username = ? AND url = ?", (username, url))
        conn.commit()
        conn.close()
        st.rerun()

st.divider()

# --- UI: STEP 3 (EXECUTION) ---
st.subheader("🔍 Step 3: Run AI Refresh")
if st.button("🔥 START MULTI-SITE SCAN", type="primary", use_container_width=True):
    keywords = get_user_keywords(username)
    
    if not user_urls or not keywords:
        st.error("Please add keywords and URLs first.")
    else:
        all_results = []
        progress = st.progress(0)
        status_log = st.empty()
        
        for i, url in enumerate(user_urls):
            status_log.info(f"AI is analyzing: {url}...")
            
            # --- LLM SCRAPER CALL ---
            df = generic_scraper(url, keywords)
            
            if not df.empty:
                df["Company URL"] = url
                all_results.append(df)
            
            # --- RATE LIMIT PROTECTION ---
            # Essential for Free OpenRouter models (Llama 3.3 70B)
            time.sleep(3) 
            progress.progress((i+1)/len(user_urls))
        
        status_log.empty()
        
        if all_results:
            final_df = pd.concat(all_results).drop_duplicates()
            st.success(f"Scan complete! Found {len(final_df)} potential matches.")
            st.dataframe(final_df, use_container_width=True)
            
            # Excel Download Buffer
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                final_df.to_excel(writer, index=False)
            
            st.download_button(
                label="📥 Download Excel Report",
                data=output.getvalue(),
                file_name=f"{username}_job_scan_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.warning("No new matching jobs found on these sites.")
