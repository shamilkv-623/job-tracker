import streamlit as st
import pandas as pd
import bcrypt
import requests
from bs4 import BeautifulSoup
from sqlalchemy import text  # Added this import

# ---------------- CONFIG ----------------
st.set_page_config(page_title="Horizon AI | Career Monitor", layout="wide", page_icon="🚀")

# ---------------- DB CONNECTION ----------------
@st.cache_resource
def get_connection():
    try:
        return st.connection("postgresql", type="sql")
    except Exception as e:
        st.error("Database connection failed. Check your secrets.toml.")
        return None

conn = get_connection()

# --- INITIALIZE DATABASE TABLE ---
def init_db():
    if conn is not None:
        with conn.session as s:
            # Wrapped the query in text() to solve the ArgumentError
            s.execute(text("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL,
                    keywords TEXT
                )
            """))
            s.commit()

init_db()

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
    if conn is None: return None
    # Using text() for consistency and security
    query = text("SELECT id, email, password, keywords FROM users WHERE email = :email")
    res = conn.query(query, params={"email": str(email)}, ttl=0)
    return res.iloc[0] if not res.empty else None

def register_user(email: str, password: str):
    if conn is None: return False, "No DB Connection"
    hashed = hash_password(password)
    try:
        with conn.session as s:
            s.execute(
                text("INSERT INTO users (email, password) VALUES (:email, :password)"),
                {"email": email, "password": hashed},
            )
            s.commit()
        return True, "Success"
    except Exception as e:
        return False, str(e)

def update_user_keywords(user_id: int, keywords: str):
    if conn is not None:
        with conn.session as s:
            s.execute(
                text("UPDATE users SET keywords = :keywords WHERE id = :id"),
                {"keywords": keywords, "id": user_id},
            )
            s.commit()

# ---------------- SCRAPER ----------------
def quick_scrape(url: str):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")
        jobs = []
        for a in soup.find_all("a"):
            href = (a.get("href") or "").lower()
            text_content = a.get_text(strip=True)
            if any(k in href for k in ["job", "career", "opening"]):
                if text_content:
                    jobs.append(text_content)
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

# ---------------- UI LOGIC ----------------
if not st.session_state.logged_in:
    st.title("🚀 Horizon AI - Career Monitor")
    tab1, tab2 = st.tabs(["Login", "Sign Up"])

    with tab1:
        with st.form("login_form"):
            email_input = st.text_input("Email")
            pass_input = st.text_input("Password", type="password")
            if st.form_submit_button("Login"):
                user = get_user_by_email(email_input)
                if user is not None and check_password(pass_input, user.password):
                    st.session_state.logged_in = True
                    st.session_state.user_id = int(user.id)
                    st.session_state.user_email = user.email
                    st.session_state.user_data = user
                    st.rerun()
                else:
                    st.error("Invalid credentials")

    with tab2:
        with st.form("signup_form"):
            reg_email = st.text_input("New Email")
            reg_pass = st.text_input("New Password", type="password")
            if st.form_submit_button("Register"):
                success, msg = register_user(reg_email, reg_pass)
                if success:
                    st.success("Account created! Please login.")
                else:
                    st.error(f"Error: {msg}")

else:
    # --- DASHBOARD ---
    st.sidebar.title("Settings")
    st.sidebar.write(f"User: {st.session_state.user_email}")
    if st.sidebar.button("Logout"):
        st.session_state.clear()
        st.rerun()

    st.title("📊 Career Monitor Dashboard")
    
    col1, col2 = st.columns([2, 1])
    with col1:
        st.subheader("🔎 Live Job Scanner")
        target_url = st.text_input("Enter company careers page URL")
        if st.button("Scan Jobs"):
            with st.spinner("Scanning..."):
                results = quick_scrape(target_url)
                for job in results:
                    st.write(f"✅ {job}")

    with col2:
        st.subheader("👤 Profile")
        u_data = st.session_state.user_data
        curr_keys = getattr(u_data, 'keywords', "") or ""
        
        new_keys = st.text_area("Target Roles", value=curr_keys)
        if st.button("Save Keywords"):
            update_user_keywords(st.session_state.user_id, new_keys)
            st.session_state.user_data = get_user_by_email(st.session_state.user_email)
            st.rerun()
