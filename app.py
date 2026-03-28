import streamlit as st
import pandas as pd
import bcrypt
import requests
from bs4 import BeautifulSoup

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
    query = """
    SELECT id, email, password, keywords
    FROM users
    WHERE email = :email
    """
    try:
        res = conn.query(query, params={"email": str(email)}, ttl=0)
        return res.iloc[0] if not res.empty else None
    except Exception as e:
        st.error(f"DB Error (fetch user): {e}")
        return None

def register_user(email: str, password: str):
    hashed = hash_password(password)
    try:
        with conn.session as s:
            s.execute(
                """
                INSERT INTO users (email, password)
                VALUES (:email, :password)
                """,
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
                """
                UPDATE users
                SET keywords = :keywords
                WHERE id = :id
                """,
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
            text = a.get_text(strip=True)
            if any(k in href for k in ["job", "career", "opening"]):
                if text:
                    jobs.append(text)

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
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Login")

            if submit:
                user = get_user_by_email(email)

                if user is None:
                    st.error("User not found")
                elif check_password(password, user.password):
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
            email = st.text_input("New Email")
            password = st.text_input("New Password", type="password")
            submit = st.form_submit_button("Register")

            if submit:
                if not email or not password:
                    st.warning("Please fill all fields")
                else:
                    success, error = register_user(email, password)

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
        url = st.text_input("Enter company careers page URL")

        if st.button("Scan Jobs"):
            with st.spinner("Scanning..."):
                jobs = quick_scrape(url)
                for job in jobs:
                    st.write(f"✅ {job}")

    # -------- PROFILE --------
    with col2:
        st.subheader("👤 Profile")

        user_data = st.session_state.user_data
        current_keywords = user_data.keywords if user_data.keywords else ""

        with st.expander("Update Keywords"):
            new_keywords = st.text_area("Target Roles", value=current_keywords)

            if st.button("Save Keywords"):
                update_user_keywords(st.session_state.user_id, new_keywords)
                st.success("Updated successfully")

                # refresh session
                st.session_state.user_data = get_user_by_email(st.session_state.user_email)
                st.rerun()

    st.divider()

    st.subheader("🤖 Tracking Summary")
    st.info(f"Tracking roles: {current_keywords if current_keywords else 'None'}")
