import streamlit as st
import pandas as pd
import bcrypt
import requests
import io
from bs4 import BeautifulSoup
from sqlalchemy import text
from urllib.parse import urljoin

# ---------------- CONFIG ----------------
st.set_page_config(page_title="Horizon AI | Career Monitor", layout="wide", page_icon="🚀")

# ---------------- DB CONNECTION ----------------
@st.cache_resource
def get_connection():
    # Uses [connections.postgresql] from your secrets.toml
    return st.connection("postgresql", type="sql")

conn = get_connection()

# ---------------- SYSTEM STATUS ----------------
def run_connection_test():
    st.sidebar.subheader("System Status")
    try:
        with conn.session as s:
            s.execute(text("SELECT 1"))
        st.sidebar.success("✅ Database: Connected")
    except Exception as e:
        st.sidebar.error("❌ Database: Connection Failed")

run_connection_test()

# ---------------- AUTH HELPERS ----------------
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def check_password(password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed_password.encode())
    except Exception:
        return False

# ---------------- DB FUNCTIONS ----------------

def get_user_by_email(email: str):
    query = "SELECT id, email, password, keywords, target_url FROM users WHERE email = :email"
    try:
        res = conn.query(query, params={"email": str(email)}, ttl=0)
        if not res.empty:
            return res.iloc[0].to_dict()
        return None
    except Exception as e:
        st.error(f"Auth Error: {e}")
        return None

def register_user(email: str, password: str):
    hashed = hash_password(password)
    try:
        with conn.session as s:
            s.execute(
                text("INSERT INTO users (email, password) VALUES (:email, :password)"),
                {"email": email, "password": hashed},
            )
            s.commit()
        return True, None
    except Exception as e:
        return False, str(e)

def update_user_settings(user_id: int, keywords: str, url: str):
    try:
        with conn.session as s:
            s.execute(
                text("UPDATE users SET keywords = :keywords, target_url = :url WHERE id = :id"),
                {"keywords": keywords, "url": url, "id": user_id},
            )
            s.commit()
        return True
    except Exception as e:
        st.error(f"Save Error: {e}")
        return False

# ---------------- SCRAPER (LIST-BASED IDEA) ----------------
def quick_scrape(url: str, keywords_str: str):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Clean keywords from user profile
        keyword_list = [k.strip().lower() for k in keywords_str.split(",")] if keywords_str else []
        jobs = []

        # Scrape links that look like job titles or contain keywords
        for a in soup.find_all("a"):
            text_val = a.get_text(strip=True)
            href = a.get("href", "")
            
            # Match logic: Does the text contain your keywords?
            if any(k in text_val.lower() for k in keyword_list) and len(text_val) > 3:
                jobs.append({
                    "title": text_val,
                    "link": urljoin(url, href)
                })

        # Remove duplicates
        unique_jobs = {j['title']: j for j in jobs}.values()
        return list(unique_jobs)[:15]
    except Exception as e:
        return [{"title": f"Error: {str(e)}", "link": "#"}]

# ---------------- SESSION MANAGEMENT ----------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_id = None
    st.session_state.user_email = None
    st.session_state.user_data = None

# ---------------- AUTHENTICATION UI ----------------
if not st.session_state.logged_in:
    st.title("🚀 Horizon AI - Career Monitor")
    tab1, tab2 = st.tabs(["Login", "Sign Up"])

    with tab1:
        with st.form("login_form"):
            email_in = st.text_input("Email")
            pass_in = st.text_input("Password", type="password")
            if st.form_submit_button("Access Dashboard"):
                user = get_user_by_email(email_in)
                if user and check_password(pass_in, user['password']):
                    st.session_state.logged_in = True
                    st.session_state.user_id = int(user['id'])
                    st.session_state.user_email = user['email']
                    st.session_state.user_data = user
                    st.rerun()
                else:
                    st.error("Invalid Credentials")

    with tab2:
        with st.form("signup_form"):
            email_reg = st.text_input("Preferred Email")
            pass_reg = st.text_input("Create Password", type="password")
            if st.form_submit_button("Create Account"):
                success, error = register_user(email_reg, pass_reg)
                if success: st.success("Success! Please Login.")
                else: st.error(error)

# ---------------- MAIN DASHBOARD ----------------
else:
    st.sidebar.write(f"Logged in: **{st.session_state.user_email}**")
    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.rerun()

    st.title("📊 Career Monitor Dashboard")

    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("🔎 Live Job Scanner")
        u_data = st.session_state.user_data
        curr_url = u_data.get('target_url', "") if u_data else ""
        curr_keys = u_data.get('keywords', "") if u_data else ""

        url_input = st.text_input("Enter Company Careers URL", value=curr_url)
        
        if st.button("Manual Scan Now"):
            with st.spinner("Searching..."):
                found_jobs = quick_scrape(url_input, curr_keys)
                if found_jobs:
                    st.markdown("### Relevant Jobs Found:")
                    for job in found_jobs:
                        st.markdown(f"- **{job['title']}** \n  [Open Link]({job['link']})")
                else:
                    st.info("No matching jobs found on this page.")

    with col2:
        st.subheader("👤 Your Profile")
        with st.expander("Update Monitoring Settings", expanded=True):
            new_url = st.text_input("Default Website to Monitor", value=curr_url)
            new_keys = st.text_area("Keywords (comma separated)", value=curr_keys)
            if st.button("Save Profile Settings"):
                if update_user_settings(st.session_state.user_id, new_keys, new_url):
                    st.session_state.user_data = get_user_by_email(st.session_state.user_email)
                    st.success("Settings Saved!")
                    st.rerun()

    st.divider()

    # --- THE EXCEL & MONITOR STATUS SECTION ---
    st.subheader("📄 Daily Excel Intelligence (24h Update)")
    
    try:
        # Fetch only THIS user's data
        report_data = conn.query(
            "SELECT job_title, company_name, location, link, extracted_at FROM daily_excel_data WHERE user_id = :uid ORDER BY extracted_at DESC",
            params={"uid": st.session_state.user_id},
            ttl=0
        )

        if not report_data.empty:
            # RUNNING STATUS BUTTON
            st.button("🟢 Monitor Status: Active & Running", disabled=True)
            
            last_run = report_data['extracted_at'].max()
            st.success(f"✅ Excel Report Ready (Last updated: {last_run.strftime('%Y-%m-%d')})")
            
            with st.expander("📝 View Found Jobs as List"):
                for index, row in report_data.iterrows():
                    st.markdown(f"**{row['job_title']}** | {row['location']}")
                    st.caption(f"[Apply]({row['link']})")
                    st.write("---")

            # EXCEL GENERATION
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                report_data.to_excel(writer, index=False, sheet_name='Job_Tracker')
            
            st.download_button(
                label="📥 Download Daily Excel Sheet",
                data=buffer.getvalue(),
                file_name=f"Job_Tracker_Daily_{last_run.strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        else:
            # WAITING STATUS
            st.info("🟡 Monitor Status: Waiting for next 24h background scan...")
            
    except Exception:
        st.warning("Daily system is initializing...")

    st.divider()
    st.subheader("🤖 Active Configuration")
    st.code(f"Site: {curr_url}\nKeys: {curr_keys}")
