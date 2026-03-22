import streamlit as st
import pandas as pd
import bcrypt
import time
from io import BytesIO
from datetime import datetime
from sqlalchemy import text

# Import your engine
from scraper_engine import smart_scraper 
from utils import extract_text_from_pdf, extract_keywords_from_cv

# --- 1. DATABASE CONNECTION ---
# This uses the connection string in your .streamlit/secrets.toml
conn = st.connection("postgresql", type="sql")

def add_user(username, password):
    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    try:
        with conn.session as s:
            s.execute(
                text("INSERT INTO users (username, password, keywords) VALUES (:u, :p, :k)"),
                {"u": username, "p": hashed, "k": ""}
            )
            s.commit()
        return True
    except Exception:
        return False

def check_user(username, password):
    res = conn.query("SELECT password FROM users WHERE username = :u", 
                     params={"u": username}, ttl=0)
    if not res.empty:
        hashed = res.iloc[0]['password']
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    return False

def get_user_keywords(username):
    res = conn.query("SELECT keywords FROM users WHERE username = :u", 
                     params={"u": username}, ttl=0)
    if not res.empty and res.iloc[0]['keywords']:
        return [k.strip() for k in res.iloc[0]['keywords'].split(",") if k.strip()]
    return []

def save_user_keywords(username, kw_list):
    with conn.session as s:
        s.execute(
            text("UPDATE users SET keywords = :k WHERE username = :u"),
            {"k": ",".join(kw_list), "u": username}
        )
        s.commit()

def get_user_urls(username):
    df = conn.query("SELECT url FROM urls WHERE username = :u", 
                    params={"u": username}, ttl=0)
    return df['url'].tolist() if not df.empty else []

# --- 2. APP CONFIG ---
st.set_page_config(page_title="Horizon AI | Career Monitor", layout="wide", page_icon="🚀")

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = ""

# --- 3. LOGIN / SIGNUP UI ---
if not st.session_state.logged_in:
    st.title("🔐 AI Job Tracker Login (Cloud)")
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
            text_cv = extract_text_from_pdf(uploaded_file)
            updated_kw.extend(extract_keywords_from_cv(text_cv))
    
    final_kw_list = list(set(updated_kw))
    save_user_keywords(username, final_kw_list)
    st.success("Profile Updated!")
    st.rerun()

st.divider()

# --- UI: STEP 2 (URLS) ---
st.subheader("🌐 Step 2: Your Tracked Companies")
new_url = st.text_input("Add Career Portal URL")
if st.button("➕ Add to My List"):
    if new_url:
        try:
            with conn.session as s:
                s.execute(text("INSERT INTO urls (username, url) VALUES (:u, :url)"),
                          {"u": username, "url": new_url})
                s.commit()
            st.rerun()
        except: st.warning("Site already in your list.")

user_urls = get_user_urls(username)
for i, url in enumerate(user_urls):
    c1, c2 = st.columns([9, 1])
    c1.caption(f"📍 {url}")
    if c2.button("🗑️", key=f"del_{i}"):
        with conn.session as s:
            s.execute(text("DELETE FROM urls WHERE username = :u AND url = :url"),
                      {"u": username, "url": url})
            s.commit()
        st.rerun()

st.divider()

# --- NEW SECTION: AUTOMATED RESULTS ---
st.subheader("🔔 Found by 24h Bot")
auto_df = conn.query("SELECT job_title, company_url, date_found FROM scan_results WHERE username = :u ORDER BY date_found DESC", 
                     params={"u": username}, ttl=0)

if not auto_df.empty:
    st.dataframe(auto_df, use_container_width=True)
else:
    st.info("The automated scanner hasn't found any new matches yet.")

st.divider()

# --- UI: STEP 3 (MANUAL EXECUTION) ---
st.subheader("🔍 Step 3: Run Immediate AI Refresh")
if st.button("🔥 START MULTI-SITE SCAN", type="primary", use_container_width=True):
    keywords = get_user_keywords(username)
    if not user_urls or not keywords:
        st.error("Please add keywords and URLs first.")
    else:
        all_results = []
        progress_bar = st.progress(0)
        with st.status("🚀 Multi-Site AI Scan in Progress...", expanded=True) as status:
            for i, url in enumerate(user_urls):
                status.write(f"Analyzing: {url}...")
                df = smart_scraper(url, keywords)
                if not df.empty:
                    df["Company URL"] = url
                    all_results.append(df)
                progress_bar.progress((i + 1) / len(user_urls))
                time.sleep(1.5) 
            status.update(label="✅ Scan Complete!", state="complete", expanded=False)

        if all_results:
            final_df = pd.concat(all_results, ignore_index=True).drop_duplicates()
            st.success(f"Found {len(final_df)} potential matches.")
            st.dataframe(final_df, use_container_width=True)
            
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
            st.warning("No matching jobs found across these sites.")
