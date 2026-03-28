import streamlit as st
import pandas as pd
import bcrypt
import requests
from bs4 import BeautifulSoup
from sqlalchemy import text  # 1. IMPORT ADDED HERE

# ---------------- CONFIG ----------------
st.set_page_config(page_title="Horizon AI | Career Monitor", layout="wide", page_icon="🚀")

# ---------------- DB CONNECTION ----------------
@st.cache_resource
def get_connection():
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
    # 2. WRAPPED IN text()
    query = text("""
    SELECT id, email, password, keywords 
    FROM users 
    WHERE email = :email
    """)
    try:
        # Note: conn.query() handles the string-to-text conversion internally 
        # but for .execute() and consistency, we use text()
        res = conn.query(query, params={"email": str(email)}, ttl=0)
        return res.iloc[0] if not res.empty else None
    except Exception as e:
        st.error(f"DB Error (fetch user): {e}")
        return None

def register_user(email: str, password: str):
    hashed = hash_password(password)
    try:
        with conn.session as s:
            # 3. WRAPPED IN text()
            s.execute(
                text("""
                INSERT INTO users (email, password) 
                VALUES (:email, :password)
                """),
                {"email": email, "password": hashed},
            )
            s.commit()
        return True, None
    except Exception as e:
        return False, str(e)

def update_user_keywords(user_id: int, keywords: str):
    try:
        with conn.session as s:
            # 4. WRAPPED IN text()
            s.execute(
                text("""
                UPDATE users 
                SET keywords = :keywords 
                WHERE id = :id
                """),
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
            if any(k in href for k in ["job", "career", "opening"]):
                if text_val:
                    jobs.append(text_val)

        return list(set(jobs))[:10] if jobs else ["No jobs found"]
    except Exception as e:
        return [f"Error: {str(e)}"]

# ---------------- SESSION ----------------
def init_session():
    defaults = {
        "logged_in": False,
        "user_id": None,
        "user_email": None,
        "user_data": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_session()

# ---------------- AUTH UI ----------------
if not st.session_state.logged_in:
    st.title("🚀 Horizon AI - Career Monitor")
    tab1, tab2 = st.tabs(["Login", "Sign Up"])

    # -------- LOGIN --------
    with tab1:
        with st.form("login_form"):
            email_in = st.text_input("Email")
            pass_in = st.text_input("Password", type="password")
            submit_log = st.form_submit_button("Login")

            if submit_log:
                user = get_user_by_email(email_in)
                if user is None:
                    st.error("User not found")
                elif check_password(pass_in, user.password):
                    st.session_state.logged_in = True
                    st.session_state.user_id = int(user.id)
                    st.session_state.user_email = user.email
                    st.session_state.user_data = user
                    st.success("Login successful")
                    st.rerun()
                else:
                    st.error("Incorrect password")

    # -------- SIGNUP --------
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
                            st.error("User already exists")
                        else:
                            st.error(f"Database Error: {error}")

# ---------------- MAIN APP ----------------
else:
    st.sidebar.title("Settings")
    st.sidebar.write(f"Logged in as: {st.session_state.user_email}")

    if st.sidebar.button("Logout"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

    st.title("📊 Career Monitor Dashboard")

    col1, col2 = st.columns([2, 1])

    # -------- JOB SCANNER --------
    with col1:
        st.subheader("🔎 Live Job Scanner")
        url_input = st.text_input("Enter company careers page URL")

        if st.button("Scan Jobs"):
            if url_input:
                with st.spinner("Scanning..."):
                    jobs = quick_scrape(url_input)
                    for job in jobs:
                        st.write(f"✅ {job}")
            else:
                st.warning("Please enter a URL")

    # -------- PROFILE --------
    with col2:
        st.subheader("👤 Profile")
        u_data = st.session_state.user_data
        curr_keys = u_data.keywords if (hasattr(u_data, 'keywords') and u_data.keywords) else ""

        with st.expander("Update Keywords"):
            new_keys = st.text_area("Target Roles", value=curr_keys)
            if st.button("Save Keywords"):
                update_user_keywords(st.session_state.user_id, new_keys)
                st.session_state.user_data = get_user_by_email(st.session_state.user_email)
                st.success("Updated successfully")
                st.rerun()

    st.divider()
    st.subheader("🤖 Tracking Summary")
    st.info(f"Tracking roles: {curr_keys if curr_keys else 'None'}")
