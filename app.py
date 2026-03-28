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
    # Streamlit will look for [connections.postgresql] in secrets.toml
    return st.connection("postgresql", type="sql")

conn = get_connection()

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
        # ttl=0 ensures we always get fresh data from the DB
        res = conn.query(query, params={"email": str(email)}, ttl=0)
        if not res.empty:
            # Return as a dictionary for easier attribute access
            return res.iloc[0].to_dict()
        return None
    except Exception as e:
        st.error(f"DB Error (fetch user): {e}")
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
        st.error(f"Update Error: {e}")

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
            # Filter for job-related keywords
            if any(k in href for k in ["job", "career", "opening", "vacancy"]):
                if text_val and len(text_val) > 2:
                    jobs.append(text_val)

        return list(set(jobs))[:15] if jobs else ["No jobs found on this page."]
    except Exception as e:
        return [f"Error: {str(e)}"]

# ---------------- SESSION ----------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_id = None
    st.session_state.user_email = None
    st.session_state.user_data = None

# ---------------- AUTH UI ----------------
if not st.session_state.logged_in:
    st.title("🚀 Horizon AI - Career Monitor")
    tab1, tab2 = st.tabs(["Login", "Sign Up"])

    with tab1:
        with st.form("login_form"):
            email_in = st.text_input("Email")
            pass_in = st.text_input("Password", type="password")
            submit_log = st.form_submit_button("Login")

            if submit_log:
                user = get_user_by_email(email_in)
                if user is None:
                    st.error("User not found")
                # Use user['password'] because we converted the row to a dict
                elif check_password(pass_in, user['password']):
                    st.session_state.logged_in = True
                    st.session_state.user_id = int(user['id'])
                    st.session_state.user_email = user['email']
                    st.session_state.user_data = user
                    st.success("Login successful!")
                    st.rerun()
                else:
                    st.error("Incorrect password")

    with tab2:
        with st.form("signup_form"):
            email_reg = st.text_input("New Email")
            pass_reg = st.text_input("New Password", type="password")
            submit_reg = st.form_submit_button("Register")

            if submit_reg:
                if not email_reg or not pass_reg:
                    st.warning("Please fill all fields")
                else:
                    success, error = register_user(email_reg, pass_reg)
                    if success:
                        st.success("Account created! Please login.")
                    else:
                        if "duplicate" in error.lower():
                            st.error("This email is already registered.")
                        else:
                            st.error(f"Database Error: {error}")

# ---------------- MAIN APP ----------------
else:
    st.sidebar.title("Settings")
    st.sidebar.write(f"Logged in as: **{st.session_state.user_email}**")

    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.session_state.user_id = None
        st.rerun()

    st.title("📊 Career Monitor Dashboard")

    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("🔎 Live Job Scanner")
        url_input = st.text_input("Enter company careers page URL (e.g., https://company.com/careers)")
        if st.button("Scan Jobs"):
            if url_input:
                if not url_input.startswith("http"):
                    st.error("Please include http:// or https://")
                else:
                    with st.spinner("Analyzing page content..."):
                        jobs = quick_scrape(url_input)
                        for job in jobs:
                            st.info(f"📍 {job}")
            else:
                st.warning("Please enter a URL")

    with col2:
        st.subheader("👤 Profile")
        u_data = st.session_state.user_data
        
        # Pull latest keyword data
        curr_keys = u_data.get('keywords', "") if u_data else ""

        with st.expander("Update Target Roles"):
            new_keys = st.text_area("Keywords (e.g. Quant, Python, Risk)", value=curr_keys)
            if st.button("Save Keywords"):
                update_user_keywords(st.session_state.user_id, new_keys)
                # Sync session with DB
                st.session_state.user_data = get_user_by_email(st.session_state.user_email)
                st.success("Keywords updated!")
                st.rerun()

    st.divider()
    st.subheader("🤖 Tracking Summary")
    st.write(f"Active Monitoring for: `{curr_keys if curr_keys else 'No keywords set'}`")
