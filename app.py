import streamlit as st
import pandas as pd
import bcrypt
import requests
import io
import re
from bs4 import BeautifulSoup
from sqlalchemy import text
from urllib.parse import urljoin
from datetime import datetime

# ---------------- 1. INITIAL CONFIG & SESSION ----------------
st.set_page_config(page_title="Horizon AI | Career Monitor", layout="wide", page_icon="🚀")

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_id = None
    st.session_state.user_email = None
    st.session_state.user_data = {}

# ---------------- 2. DATABASE CONNECTION ----------------
@st.cache_resource
def get_connection():
    try:
        return st.connection("postgresql", type="sql")
    except Exception as e:
        st.error("Database Connection Configuration Missing.")
        return None

conn = get_connection()

# ---------------- 3. CORE LOGIC FUNCTIONS ----------------

def extract_company_from_url(url):
    try:
        domain = url.split("//")[-1].split("/")[0]
        parts = domain.split('.')
        name = parts[1] if len(parts) > 2 else parts[0]
        return name.replace("fa", "").replace("oraclecloud", "JPMC").capitalize()
    except:
        return "Company"

def extract_location(text_val):
    # Regex to pull location after hyphens or parentheses
    match = re.search(r'[-|(|,]\s*([a-zA-Z\s]+)$', text_val)
    if match:
        return match.group(1).strip()
    return "Not Specified"

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def check_password(password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed_password.encode())
    except:
        return False

# ---------------- 4. DATABASE QUERIES ----------------

def get_user_by_email(email):
    query = "SELECT id, email, password, keywords FROM users WHERE email = :email"
    res = conn.query(query, params={"email": str(email)}, ttl=0)
    return res.iloc[0].to_dict() if not res.empty else None

def get_monitored_sites(user_id):
    return conn.query("SELECT id, url FROM monitored_sites WHERE user_id = :uid", params={"uid": user_id}, ttl=0)

def add_monitored_site(user_id, url):
    with conn.session as s:
        s.execute(text("INSERT INTO monitored_sites (user_id, url) VALUES (:uid, :url)"), {"uid": user_id, "url": url})
        s.commit()

def delete_monitored_site(site_id):
    with conn.session as s:
        s.execute(text("DELETE FROM monitored_sites WHERE id = :id"), {"id": site_id})
        s.commit()

# ---------------- 5. SCRAPER ENGINE ----------------

def run_quick_scrape(url, keywords_str, location_filter=""):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=12)
        soup = BeautifulSoup(response.text, "html.parser")
        
        keywords = [k.strip().lower() for k in keywords_str.split(",")] if keywords_str else []
        loc_f = location_filter.lower().strip()
        
        found_jobs = []
        company = extract_company_from_url(url)

        for a in soup.find_all("a"):
            title = a.get_text(strip=True)
            link = urljoin(url, a.get("href", ""))
            
            # Filtering logic
            key_match = any(k in title.lower() for k in keywords) if keywords else True
            loc_match = loc_f in title.lower() if loc_f else True
            
            if key_match and loc_match and len(title) > 8:
                found_jobs.append({
                    "title": title,
                    "link": link,
                    "company": company,
                    "location": extract_location(title)
                })
        
        # Remove duplicates
        return list({v['title']: v for v in found_jobs}.values())
    except Exception as e:
        return []

# ---------------- 6. UI: LOGIN / SIGNUP ----------------

if not st.session_state.logged_in:
    st.title("🚀 Horizon AI | Career Monitor")
    t1, t2 = st.tabs(["Login", "Create Account"])
    
    with t1:
        with st.form("l_form"):
            e_in = st.text_input("Email")
            p_in = st.text_input("Password", type="password")
            if st.form_submit_button("Login"):
                user = get_user_by_email(e_in)
                if user and check_password(p_in, user['password']):
                    st.session_state.logged_in = True
                    st.session_state.user_id = user['id']
                    st.session_state.user_email = user['email']
                    st.session_state.user_data = user
                    st.rerun()
                else:
                    st.error("Invalid email or password.")
    
    with t2:
        with st.form("s_form"):
            e_reg = st.text_input("Email Address")
            p_reg = st.text_input("Create Password", type="password")
            if st.form_submit_button("Register"):
                hashed = hash_password(p_reg)
                with conn.session as s:
                    s.execute(text("INSERT INTO users (email, password) VALUES (:e, :p)"), {"e": e_reg, "p": hashed})
                    s.commit()
                st.success("Account created! Please login.")

# ---------------- 7. UI: MAIN DASHBOARD ----------------

else:
    st.title("📊 Career Monitor Dashboard")
    
    # Sidebar for Profile and Logout
    st.sidebar.header(f"Welcome, {st.session_state.user_email.split('@')[0]}")
    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.rerun()

    col1, col2 = st.columns([2, 1])

    # LEFT COLUMN: SCANNER
    with col1:
        st.subheader("🔎 Live Job Scanner")
        loc_filter = st.text_input("🌍 Filter results by City/Country (Optional)", placeholder="e.g. Hyderabad")
        
        sites_df = get_monitored_sites(st.session_state.user_id)
        
        if not sites_df.empty:
            target_url = st.selectbox("Select site to scan", ["SCAN ALL"] + sites_df['url'].tolist())
            
            if st.button("▶️ Run Live Scan"):
                urls = sites_df['url'].tolist() if target_url == "SCAN ALL" else [target_url]
                all_matches = []

                for u in urls:
                    with st.status(f"Scanning {u}...", expanded=False):
                        results = run_quick_scrape(u, st.session_state.user_data.get('keywords', ""), loc_filter)
                        if results:
                            st.write(f"Found {len(results)} matches")
                            all_matches.extend(results)
                        else:
                            st.write("No new matches.")

                if all_matches:
                    with conn.session as s:
                        for job in all_matches:
                            s.execute(
                                text("""INSERT INTO daily_excel_data (user_id, job_title, company_name, location, link) 
                                        VALUES (:uid, :t, :c, :l, :link)"""),
                                {"uid": st.session_state.user_id, "t": job['title'], "c": job['company'], "l": job['location'], "link": job['link']}
                            )
                        s.commit()
                    st.success(f"Synced {len(all_matches)} jobs to Excel!")
                    st.rerun()
        else:
            st.info("Start by adding a careers URL in the sidebar.")

    # RIGHT COLUMN: MANAGEMENT
    with col2:
        st.subheader("⚙️ Monitor Settings")
        
        with st.expander("Update Keywords"):
            k_input = st.text_area("Keywords (comma separated)", value=st.session_state.user_data.get('keywords', ""))
            if st.button("Save Keywords"):
                with conn.session as s:
                    s.execute(text("UPDATE users SET keywords = :k WHERE id = :id"), {"k": k_input, "id": st.session_state.user_id})
                    s.commit()
                st.session_state.user_data['keywords'] = k_input
                st.success("Keywords updated!")

        with st.expander("Manage Sites", expanded=True):
            new_site = st.text_input("Add Careers URL")
            if st.button("Add"):
                add_monitored_site(st.session_state.user_id, new_site)
                st.rerun()
            
            st.divider()
            for _, row in sites_df.iterrows():
                c1, c2 = st.columns([4, 1])
                c1.caption(row['url'])
                if c2.button("🗑️", key=f"del_{row['id']}"):
                    delete_monitored_site(row['id'])
                    st.rerun()

    # FOOTER: EXCEL DOWNLOAD
    st.divider()
    st.subheader("📄 Daily Excel Intelligence")
    excel_data = conn.query("SELECT job_title, company_name, location, link, extracted_at FROM daily_excel_data WHERE user_id = :uid ORDER BY extracted_at DESC", params={"uid": st.session_state.user_id}, ttl=0)
    
    if not excel_data.empty:
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            excel_data.to_excel(writer, index=False, sheet_name='Sheet1')
        
        st.download_button(
            label="📥 Download Excel Report",
            data=buffer.getvalue(),
            file_name=f"Job_Tracker_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
    else:
        st.info("No data yet. Run a scan to populate your Excel report.")
