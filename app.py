import streamlit as st
import pandas as pd
import bcrypt
import requests
import io
from bs4 import BeautifulSoup
from sqlalchemy import text

# ---------------- CONFIG ----------------
st.set_page_config(page_title="Horizon AI | Career Monitor", layout="wide", page_icon="🚀")

# ---------------- DB CONNECTION ----------------
@st.cache_resource
def get_connection():
    # Streamlit looks for [connections.postgresql] in secrets.toml
    return st.connection("postgresql", type="sql")

conn = get_connection()

# ---------------- DEBUGGING TOOL ----------------
def run_connection_test():
    """Tests the connection and displays results in the sidebar."""
    st.sidebar.subheader("System Status")
    try:
        with conn.session as s:
            s.execute(text("SELECT 1"))
        st.sidebar.success("✅ Database: Connected")
    except Exception as e:
        st.sidebar.error("❌ Database: Connection Failed")
        with st.sidebar.expander("View Error Details"):
            st.code(str(e))

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
    query = "SELECT id, email, password, keywords FROM users WHERE email = :email"
    try:
        res = conn.query(query, params={"email": str(email)}, ttl=0)
        if not res.empty:
            return res.iloc[0].to_dict()
        return None
    except Exception as e:
        st.error(f"Authentication Error: {e}")
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

def update_user_keywords(user_id: int, keywords: str):
    try:
        with conn.session as s:
            s.execute(
                text("UPDATE users SET keywords = :keywords WHERE id = :id"),
                {"keywords": keywords, "id": user_id},
            )
            s.commit()
    except Exception as e:
        st.error(f"Profile Update Error: {e}")

# ---------------- SCRAPER (MANUAL) ----------------
def quick_scrape(url: str):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")

        jobs = []
        for a in soup.find_all("a"):
            href = (a.get("href") or "").lower()
            text_val = a.get_text(strip=True)
            if any(k in href for k in ["job", "career", "opening", "vacancy", "position"]):
                if text_val and len(text_val) > 2:
                    jobs.append(text_val)

        return list(set(jobs))[:15] if jobs else ["No active openings detected."]
    except Exception as e:
        return [f"Scraper Error: {str(e)}"]

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
            submit_log = st.form_submit_button("Access Dashboard")

            if submit_log:
                user = get_user_by_email(email_in)
                if user is None:
                    st.error("User not found.")
                elif check_password(pass_in, user['password']):
                    st.session_state.logged_in = True
                    st.session_state.user_id = int(user['id'])
                    st.session_state.user_email = user['email']
                    st.session_state.user_data = user
                    st.rerun()
                else:
                    st.error("Invalid password.")

    with tab2:
        with st.form("signup_form"):
            email_reg = st.text_input("Preferred Email")
            pass_reg = st.text_input("Create Password", type="password")
            submit_reg = st.form_submit_button("Create Account")
            if submit_reg:
                success, error = register_user(email_reg, pass_reg)
                if success: st.success("Success! Please Login.")
                else: st.error(f"Error: {error}")

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
        url_input = st.text_input("Enter Company Careers URL")
        if st.button("Manual Scan"):
            with st.spinner("Fetching..."):
                jobs = quick_scrape(url_input)
                for job in jobs: st.info(f"📍 {job}")

    with col2:
        st.subheader("👤 Your Profile")
        u_data = st.session_state.user_data
        curr_keys = u_data.get('keywords', "") if u_data else ""

        with st.expander("Update Monitoring Keywords"):
            new_keys = st.text_area("Keywords (comma separated)", value=curr_keys)
            if st.button("Save Changes"):
                update_user_keywords(st.session_state.user_id, new_keys)
                st.session_state.user_data = get_user_by_email(st.session_state.user_email)
                st.success("Keywords updated!")
                st.rerun()

    st.divider()

    # --- PERSONALIZED 24H AUTOMATED EXCEL SECTION ---
    st.subheader("📄 Daily Excel Intelligence (24h Update)")
    
    try:
        # Fetch data specifically for THIS user from the new table
        report_data = conn.query(
            """
            SELECT job_title, company_name, location, link, extracted_at 
            FROM daily_excel_data 
            WHERE user_id = :uid 
            ORDER BY extracted_at DESC
            """,
            params={"uid": st.session_state.user_id},
            ttl=0
        )

        if not report_data.empty:
            last_run = report_data['extracted_at'].max()
            st.success(f"✅ Your 24h update is ready! (Last scan: {last_run.strftime('%Y-%m-%d %H:%M')})")
            
            # Data Preview for User Confidence
            with st.expander("🔍 Preview Matches Found"):
                st.dataframe(report_data, use_container_width=True)

            # Excel Generation
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                report_data.to_excel(writer, index=False, sheet_name='Job_Tracker_Daily')
            
            # Download Button
            st.download_button(
                label="📥 Download My Personal Job Report (Excel)",
                data=buffer.getvalue(),
                file_name=f"My_Job_Report_{last_run.strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        else:
            st.info("🕒 Your personalized background monitor is active. Your report will appear here once the next 24h scan finds matches for your keywords.")
            
    except Exception as e:
        st.warning("Daily Intelligence System is initializing. Please ensure your background worker has run once.")

    st.divider()
    st.subheader("🤖 Current Settings")
    st.write(f"Active monitoring keywords: `{curr_keys if curr_keys else 'None Set'}`")
