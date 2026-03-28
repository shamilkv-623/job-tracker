import streamlit as st
import pandas as pd
import bcrypt
import requests
from bs4 import BeautifulSoup
from sqlalchemy import text

# --- CONFIGURATION ---
st.set_page_config(page_title="Horizon AI | Career Monitor", layout="wide", page_icon="🚀")

# --- DATABASE CONNECTION ---
try:
    conn = st.connection("postgresql", type="sql")
except Exception as e:
    st.error("⚠️ Database Connection Error. Check your Streamlit Secrets.")
    st.stop()

# --- UTILITY FUNCTIONS ---
def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def check_password(password, hashed_password):
    try:
        return bcrypt.checkpw(password.encode(), hashed_password.encode())
    except Exception:
        return False

def get_user_by_email(email):
    query = text("SELECT id, email, password, keywords FROM users WHERE email = :email")
    res = conn.query(query, params={"email": email})
    return res.iloc[0] if not res.empty else None

def register_user(email, password):
    hashed = hash_password(password)
    with conn.session as s:
        s.execute(
            text("INSERT INTO users (email, password) VALUES (:email, :password)"),
            {"email": email, "password": hashed}
        )
        s.commit()

def update_user_keywords(user_id, keywords):
    with conn.session as s:
        s.execute(
            text("UPDATE users SET keywords = :keywords WHERE id = :id"),
            {"keywords": keywords, "id": user_id}
        )
        s.commit()

# --- SCRAPER LOGIC ---
def quick_scrape(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        jobs = [a.get_text(strip=True) for a in soup.find_all('a') if any(k in a.get('href', '').lower() for k in ['job', 'career'])]
        return list(set(jobs))[:5]
    except Exception as e:
        return [f"Error: {str(e)}"]

# --- SESSION STATE ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user_id' not in st.session_state:
    st.session_state.user_id = None
if 'user_email' not in st.session_state:
    st.session_state.user_email = None

# --- UI: AUTHENTICATION ---
if not st.session_state.logged_in:
    st.title("Welcome to Horizon AI")
    auth_tab1, auth_tab2 = st.tabs(["Login", "Sign Up"])

    with auth_tab1:
        with st.form("login"):
            email_in = st.text_input("Email")
            pwd_in = st.text_input("Password", type="password")
            if st.form_submit_button("Login"):
                user = get_user_by_email(email_in)
                if user is not None and check_password(pwd_in, user.password):
                    st.session_state.logged_in = True
                    st.session_state.user_id = int(user.id)
                    st.session_state.user_email = user.email
                    st.rerun()
                else:
                    st.error("Invalid credentials")

    with auth_tab2:
        with st.form("signup"):
            new_email = st.text_input("New Email")
            new_pwd = st.text_input("New Password", type="password")
            if st.form_submit_button("Register"):
                try:
                    register_user(new_email, new_pwd)
                    st.success("Account created! Please login.")
                except Exception:
                    st.error("Registration failed. Email might already exist.")

# --- UI: MAIN DASHBOARD ---
else:
    st.sidebar.title("Settings")
    st.sidebar.write(f"User: {st.session_state.user_email}")
    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.rerun()

    st.title("🚀 Career Monitor Dashboard")
    
    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("Live Job Scan")
        target_url = st.text_input("Enter Company Career URL")
        if st.button("START SCAN NOW", type="primary"):
            with st.spinner("Scanning..."):
                results = quick_scrape(target_url)
                for job in results:
                    st.write(f"✅ {job}")

    with col2:
        st.subheader("Your Profile")
        # Fetch current keywords from DB
        user_data = get_user_by_email(st.session_state.user_email)
        current_keywords = user_data.keywords if user_data.keywords else ""
        
        with st.expander("Update Keywords"):
            new_keywords = st.text_area("Target Roles", value=current_keywords, height=100)
            if st.button("Save Keywords"):
                update_user_keywords(st.session_state.user_id, new_keywords)
                st.success("Keywords saved to your profile!")
                st.rerun()

    st.divider()
    st.subheader("Automated Tracking")
    st.info(f"Bot is tracking roles: **{current_keywords if current_keywords else 'None set'}**")
