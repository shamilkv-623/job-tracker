import streamlit as st
import pandas as pd
import bcrypt
import requests
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
        # Simple query to check if the 'Tenant' exists and password is correct
        with conn.session as s:
            s.execute(text("SELECT 1"))
        st.sidebar.success("✅ Database: Connected")
    except Exception as e:
        st.sidebar.error("❌ Database: Connection Failed")
        with st.sidebar.expander("View Error Details"):
            st.code(str(e))
        
        # Specific hint for your current error
        if "Tenant or user not found" in str(e):
            st.sidebar.warning("CRITICAL: Your Project Ref in secrets.toml does not match your new Supabase project ID.")

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
            # Convert row to dictionary for reliable attribute access
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

# ---------------- SCRAPER ----------------
def quick_scrape(url: str):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")

        jobs = []
        for a in soup.find_all("a"):
            href = (a.get("href") or "").lower()
            text_val = a.get_text(strip=True)
            # Targets typical career page links
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
    st.info("Log in to track job openings and manage your career keywords.")
    
    tab1, tab2 = st.tabs(["Login", "Sign Up"])

    with tab1:
        with st.form("login_form"):
            email_in = st.text_input("Email")
            pass_in = st.text_input("Password", type="password")
            submit_log = st.form_submit_button("Access Dashboard")

            if submit_log:
                user = get_user_by_email(email_in)
                if user is None:
                    st.error("User not found. Please sign up.")
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
                if not email_reg or not pass_reg:
                    st.warning("All fields are required.")
                else:
                    success, error = register_user(email_reg, pass_reg)
                    if success:
                        st.success("Registration successful! Switch to the Login tab.")
                    else:
                        if "duplicate" in error.lower():
                            st.error("This email is already registered.")
                        else:
                            st.error(f"Registration Error: {error}")

# ---------------- MAIN DASHBOARD ----------------
else:
    st.sidebar.write(f"Logged in: **{st.session_state.user_email}**")

    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.session_state.user_id = None
        st.rerun()

    st.title("📊 Career Monitor Dashboard")

    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("🔎 Live Job Scanner")
        url_input = st.text_input("Enter Company Careers URL", placeholder="https://careers.google.com/jobs/results/")
        if st.button("Scan Now"):
            if url_input:
                if not url_input.startswith("http"):
                    st.error("Please provide a valid URL starting with http:// or https://")
                else:
                    with st.spinner("Fetching latest updates..."):
                        jobs = quick_scrape(url_input)
                        for job in jobs:
                            st.info(f"📍 {job}")
            else:
                st.warning("Please enter a URL to scan.")

    with col2:
        st.subheader("👤 Your Profile")
        u_data = st.session_state.user_data
        
        # Get latest keywords from session or DB
        curr_keys = u_data.get('keywords', "") if u_data else ""

        with st.expander("Update Monitoring Keywords"):
            new_keys = st.text_area("Example: Python, Quant Research, Risk Management", value=curr_keys)
            if st.button("Save Changes"):
                update_user_keywords(st.session_state.user_id, new_keys)
                # Refresh session state
                st.session_state.user_data = get_user_by_email(st.session_state.user_email)
                st.success("Keywords updated!")
                st.rerun()

    st.divider()
    st.subheader("🤖 Active Tracking Summary")
    st.write(f"Currently monitoring for: `{curr_keys if curr_keys else 'General Openings'}`")
