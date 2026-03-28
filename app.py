import streamlit as st
import pandas as pd
import bcrypt
import requests
import io
from bs4 import BeautifulSoup
from sqlalchemy import text
from urllib.parse import urljoin
from datetime import datetime

# ---------------- CONFIG ----------------
st.set_page_config(page_title="Horizon AI | Career Monitor", layout="wide", page_icon="🚀")

# ---------------- DB CONNECTION ----------------
@st.cache_resource
def get_connection():
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

def get_monitored_sites(user_id):
    return conn.query("SELECT id, url FROM monitored_sites WHERE user_id = :uid", params={"uid": user_id}, ttl=0)

def add_monitored_site(user_id, url):
    try:
        with conn.session as s:
            s.execute(
                text("INSERT INTO monitored_sites (user_id, url) VALUES (:uid, :url)"),
                {"uid": user_id, "url": url}
            )
            s.commit()
        return True
    except Exception as e:
        st.error(f"Error adding site: {e}")
        return False

# ---------------- SCRAPER ----------------
def quick_scrape(url: str, keywords_str: str):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")
        keyword_list = [k.strip().lower() for k in keywords_str.split(",")] if keywords_str else []
        jobs = []
        for a in soup.find_all("a"):
            text_val = a.get_text(strip=True)
            href = a.get("href", "")
            if any(k in text_val.lower() for k in keyword_list) and len(text_val) > 3:
                jobs.append({"title": text_val, "link": urljoin(url, href)})
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

    with col2:
        st.subheader("👤 Your Profile")
        with st.expander("Update Keywords", expanded=True):
            curr_keys = st.session_state.user_data.get('keywords', "")
            new_keys = st.text_area("Keywords (comma separated)", value=curr_keys)
            if st.button("Save Keywords"):
                update_user_settings(st.session_state.user_id, new_keys, "")
                st.session_state.user_data['keywords'] = new_keys
                st.success("Keywords Saved!")

        st.divider()
        st.subheader("🔗 Monitored Sites")
        new_site = st.text_input("Add Company Careers URL")
        if st.button("➕ Add Site"):
            if new_site:
                if add_monitored_site(st.session_state.user_id, new_site):
                    st.success("Added to 24h scan list!")
                    st.rerun()

        sites_df = get_monitored_sites(st.session_state.user_id)
        for index, row in sites_df.iterrows():
            st.caption(f"📍 {row['url']}")

    with col1:
        st.subheader("🔎 Live Job Scanner")
        if not sites_df.empty:
            all_urls = sites_df['url'].tolist()
            selected_url = st.selectbox("Select site to scan", options=["SCAN ALL"] + all_urls)
            
            if st.button("Run Scan"):
                urls_to_process = all_urls if selected_url == "SCAN ALL" else [selected_url]
                found_any = False
                
                for url in urls_to_process:
                    st.write(f"**Results for {url}:**")
                    found = quick_scrape(url, st.session_state.user_data.get('keywords', ""))
                    
                    if found and "Error" not in found[0]['title']:
                        found_any = True
                        with conn.session as s:
                            for job in found:
                                st.markdown(f"- **{job['title']}** [Open Link]({job['link']})")
                                
                                # SAVING EACH MATCH TO EXCEL TABLE IMMEDIATELY
                                s.execute(
                                    text("""INSERT INTO daily_excel_data 
                                         (user_id, job_title, company_name, location, link) 
                                         VALUES (:uid, :title, :comp, :loc, :link)"""),
                                    {
                                        "uid": st.session_state.user_id,
                                        "title": job['title'],
                                        "comp": url.split("//")[-1].split(".")[0].capitalize(),
                                        "loc": "Manual Scan",
                                        "link": job['link']
                                    }
                                )
                            s.commit()
                    else:
                        st.info(f"No matches found for {url}.")
                
                if found_any:
                    st.success("✅ Findings have been added to your Excel report below!")
                    st.rerun()
        else:
            st.warning("Please add a site in the profile section first.")

    st.divider()
    st.subheader("📄 Daily Excel Intelligence (24h Update)")
    try:
        report_data = conn.query(
            "SELECT job_title, company_name, location, link, extracted_at FROM daily_excel_data WHERE user_id = :uid ORDER BY extracted_at DESC",
            params={"uid": st.session_state.user_id}, ttl=0
        )
        if not report_data.empty:
            st.button("🟢 Monitor Status: Active & Running", disabled=True)
            last_run = report_data['extracted_at'].max()
            
            # Format dataframe for clean excel
            report_data['extracted_at'] = report_data['extracted_at'].dt.strftime('%Y-%m-%d %H:%M')
            
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                report_data.to_excel(writer, index=False, sheet_name='Job_Tracker')
            
            st.download_button(
                label="📥 Download Daily Excel Sheet",
                data=buffer.getvalue(),
                file_name=f"Job_Tracker_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        else:
            st.info("🟡 Monitor Status: Waiting for scan to find matches...")
    except Exception:
        st.warning("System initializing...")
