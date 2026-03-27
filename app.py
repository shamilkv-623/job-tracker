import streamlit as st
import pandas as pd
import bcrypt
import requests
from bs4 import BeautifulSoup
from sqlalchemy import text
from datetime import datetime

# --- CONFIGURATION ---
st.set_page_config(page_title="Horizon AI | Career Monitor", layout="wide", page_icon="🚀")

# --- DATABASE CONNECTION (Compatible with Supabase/PostgreSQL) ---
try:
    conn = st.connection("postgresql", type="sql")
except Exception as e:
    st.error("⚠️ Database Connection Error. Please configure your .streamlit/secrets.toml")
    st.stop()

# --- UTILITY FUNCTIONS ---
def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def check_password(password, hashed_password):
    return bcrypt.checkpw(password.encode(), hashed_password.encode())

def get_user_by_email(email):
    with conn.session as s:
        res = s.execute(text("SELECT id, email, password FROM users WHERE email = :email"), {"email": email}).fetchone()
        return res

def register_user(email, password):
    hashed = hash_password(password)
    with conn.session as s:
        s.execute(
            text("INSERT INTO users (email, password) VALUES (:email, :password)"),
            {"email": email, "password": hashed}
        )
        s.commit()

# --- SCRAPER LOGIC (Generic Fallback) ---
def quick_scrape(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        # Simple logic: look for links containing 'job', 'career', or 'opening'
        jobs = [a.get_text(strip=True) for a in soup.find_all('a') if 'job' in a.get('href', '').lower()]
        return list(set(jobs))[:5] # Return top 5 unique finds
    except Exception as e:
        return [f"Error: {str(e)}"]

# --- SESSION STATE ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user_id' not in st.session_state:
    st.session_state.user_id = None

# --- UI: AUTHENTICATION ---
if not st.session_state.logged_in:
    st.title("Welcome to Horizon AI")
    auth_tab1, auth_tab2 = st.tabs(["Login", "Sign Up"])

    with auth_tab1:
        with st.form("login"):
            email = st.text_input("Email")
            pwd = st.text_input("Password", type="password")
            if st.form_submit_button("Login"):
                user = get_user_by_email(email)
                if user and check_password(pwd, user.password):
                    st.session_state.logged_in = True
                    st.session_state.user_id = user.id
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
                    st.error("Email already exists.")

# --- UI: MAIN DASHBOARD ---
else:
    st.sidebar.title("Settings")
    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.rerun()

    st.title("🚀 Career Monitor Dashboard")
    
    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("Live Job Scan")
        target_url = st.text_input("Enter Company Career URL", placeholder="https://careers.google.com/jobs/results/")
        
        if st.button("START SCAN NOW", type="primary"):
            if target_url:
                with st.spinner("Analyzing site..."):
                    results = quick_scrape(target_url)
                    if results:
                        st.write("### Potential Matches Found:")
                        for job in results:
                            st.write(f"- {job}")
                    else:
                        st.warning("No jobs found with the current scraper settings.")
            else:
                st.error("Please enter a URL first.")

    with col2:
        st.subheader("Your Profile")
        with st.expander("Update Keywords"):
            keywords = st.text_area("Target Roles (e.g., Quant Research, Data Scientist)", height=100)
            if st.button("Save Keywords"):
                # Save to database logic
                st.success("Keywords updated!")

    st.divider()
    st.subheader("24h Automated Tracking")
    # Placeholder for background results stored in DB
    st.info("The automated bot checks your tracked URLs every 24 hours. Results will appear here.")
    
    # Example table display
    # df_results = conn.query(f"SELECT site_name, job_title, found_at FROM scan_results WHERE user_id = {st.session_state.user_id}")
    # st.dataframe(df_results)
