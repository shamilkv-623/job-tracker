import streamlit as st
import pandas as pd
import bcrypt
import requests
from bs4 import BeautifulSoup
from sqlalchemy import text
from datetime import datetime

# --- CONFIGURATION ---
st.set_page_config(page_title="Horizon AI | Career Monitor", layout="wide", page_icon="🚀")

# --- DATABASE CONNECTION ---
# st.connection automatically handles the URL encoding and SSL if defined in secrets.toml
try:
    conn = st.connection("postgresql", type="sql")
except Exception as e:
    st.error("⚠️ Database Connection Error. Please verify your Streamlit Secrets.")
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
    try:
        # Using conn.query is more reliable for Streamlit's execution model
        query = text("SELECT id, email, password FROM users WHERE email = :email")
        res = conn.query(query, params={"email": email})
        
        if not res.empty:
            return res.iloc[0] # Returns the first matching user as a Series
        return None
    except Exception as e:
        st.error(f"Database lookup failed: {e}")
        return None

def register_user(email, password):
    hashed = hash_password(password)
    # Use the session context manager to ensure the transaction is closed/committed properly
    with conn.session as s:
        s.execute(
            text("INSERT INTO users (email, password) VALUES (:email, :password)"),
            {"email": email, "password": hashed}
        )
        s.commit()

# --- SCRAPER LOGIC ---
def quick_scrape(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Finding links that look like job postings
        jobs = []
        for a in soup.find_all('a', href=True):
            link_text = a.get_text(strip=True)
            link_href = a['href'].lower()
            if any(keyword in link_href for keyword in ['job', 'career', 'opening', 'position']):
                if link_text:
                    jobs.append(link_text)
        
        return list(set(jobs))[:10] # Return top 10 unique finds
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
            email_input = st.text_input("Email")
            pwd_input = st.text_input("Password", type="password")
            if st.form_submit_button("Login"):
                user = get_user_by_email(email_input)
                if user is not None and check_password(pwd_input, user.password):
                    st.session_state.logged_in = True
                    st.session_state.user_id = user.id
                    st.rerun()
                else:
                    st.error("Invalid email or password")

    with auth_tab2:
        with st.form("signup"):
            new_email = st.text_input("New Email")
            new_pwd = st.text_input("New Password", type="password")
            if st.form_submit_button("Register"):
                if new_email and new_pwd:
                    try:
                        register_user(new_email, new_pwd)
                        st.success("Account created! Please login.")
                    except Exception:
                        st.error("Registration failed. The email might already be in use.")
                else:
                    st.warning("Please provide both email and password.")

# --- UI: MAIN DASHBOARD ---
else:
    st.sidebar.title("Settings")
    st.sidebar.write(f"Logged in as: {st.session_state.user_id}")
    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.session_state.user_id = None
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
                    if results and not any("Error" in r for r in results):
                        st.write("### Potential Matches Found:")
                        for job in results:
                            st.write(f"✅ {job}")
                    else:
                        st.warning(f"Could not extract specific jobs. {results[0] if results else ''}")
            else:
                st.error("Please enter a URL first.")

    with col2:
        st.subheader("Your Profile")
        with st.expander("Update Keywords"):
            keywords = st.text_area("Target Roles (e.g., Quant Research, Data Scientist)", height=100)
            if st.button("Save Keywords"):
                st.success("Keywords updated! (Logic to be linked to DB)")

    st.divider()
    st.subheader("24h Automated Tracking")
    st.info("The automated bot checks your tracked URLs every 24 hours. Results will appear here.")
