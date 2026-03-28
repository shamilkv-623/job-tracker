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

# IMPORT YOUR SEPARATE CV LOGIC
from cv_handler import extract_text_from_cv, rank_job_match, get_clean_company_name

# ---------------- 1. INITIAL CONFIG & SESSION ----------------
st.set_page_config(page_title="Horizon AI | Career Monitor", layout="wide", page_icon="🚀")

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_id = None
    st.session_state.cv_text = "" # Store extracted CV text here

conn = st.connection("postgresql", type="sql")

# ---------------- 2. AUTH HELPERS ----------------
def check_password(password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed_password.encode())
    except:
        return False

# ---------------- 3. MAIN UI ----------------

if not st.session_state.logged_in:
    st.title("🚀 Horizon AI | Career Monitor")
    # ... (Login/Signup form remains the same as your previous code)
    # [Insert your existing Login/Signup block here]
else:
    # --- SIDEBAR: CV MONITORING & SETTINGS ---
    with st.sidebar:
        st.header(f"👋 Welcome, {st.session_state.get('user_email', 'User').split('@')[0]}")
        
        st.divider()
        st.subheader("📄 CV Monitoring")
        cv_file = st.file_uploader("Upload CV (PDF) for AI Ranking", type="pdf")
        if cv_file:
            # Use logic from your separate cv_handler.py
            st.session_state.cv_text = extract_text_from_cv(cv_file)
            st.success("CV Analysis Active!")

        st.divider()
        st.subheader("🌍 Regional Settings")
        # Fetch current country from DB
        user_pref = conn.query("SELECT target_country, keywords FROM users WHERE id = :id", 
                               params={"id": st.session_state.user_id}, ttl=0)
        
        curr_country = user_pref.iloc[0]['target_country'] if not user_pref.empty else "India"
        new_country = st.selectbox("Target Country", ["India", "USA", "UK", "UAE", "Singapore"], 
                                   index=["India", "USA", "UK", "UAE", "Singapore"].index(curr_country))
        
        if st.button("Update Global Settings"):
            with conn.session as s:
                s.execute(text("UPDATE users SET target_country = :c WHERE id = :id"), 
                          {"c": new_country, "id": st.session_state.user_id})
                s.commit()
            st.rerun()

        st.divider()
        if st.sidebar.button("Logout"):
            st.session_state.logged_in = False
            st.rerun()

    # --- MAIN CONTENT: SCANNER ---
    st.title("📊 Intelligent Career Monitor")
    
    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("🔎 Live Job Scanner")
        sites_df = conn.query("SELECT id, url FROM monitored_sites WHERE user_id = :uid", 
                              params={"uid": st.session_state.user_id}, ttl=0)
        
        if not sites_df.empty:
            if st.button("🚀 Run AI-Ranked Scan"):
                all_matches = []
                keywords = user_pref.iloc[0]['keywords'] if not user_pref.empty else ""
                
                for url in sites_df['url'].tolist():
                    try:
                        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
                        soup = BeautifulSoup(resp.text, "html.parser")
                        company = get_clean_company_name(url) # Logic from cv_handler.py
                        
                        for a in soup.find_all("a"):
                            title = a.get_text(strip=True)
                            # Keyword Filter
                            if any(k.lower() in title.lower() for k in keywords.split(",")) and len(title) > 8:
                                # AI RANKING
                                score = rank_job_match(st.session_state.cv_text, title)
                                
                                all_matches.append({
                                    "title": title,
                                    "company": company,
                                    "location": new_country,
                                    "link": urljoin(url, a.get("href", "")),
                                    "score": score
                                })
                    except: continue

                # Sort matches by highest score
                all_matches = sorted(all_matches, key=lambda x: x['score'], reverse=True)

                if all_matches:
                    with conn.session as s:
                        for job in all_matches:
                            # Save with match prefix
                            s.execute(text("""INSERT INTO daily_excel_data (user_id, job_title, company_name, location, link) 
                                              VALUES (:u, :t, :c, :l, :link)"""),
                                      {"u": st.session_state.user_id, "t": f"[{job['score']}%] {job['title']}", 
                                       "c": job['company'], "l": job['location'], "link": job['link']})
                        s.commit()
                    st.success(f"Captured {len(all_matches)} ranked jobs!")
                    st.rerun()
        else:
            st.info("Add a Careers URL in the 'Manage Sites' section to start.")

    with col2:
        st.subheader("⚙️ Monitor Settings")
        with st.expander("Update Keywords"):
            k_input = st.text_area("Keywords (comma separated)", value=user_pref.iloc[0]['keywords'] if not user_pref.empty else "")
            if st.button("Save Keywords"):
                with conn.session as s:
                    s.execute(text("UPDATE users SET keywords = :k WHERE id = :id"), {"k": k_input, "id": st.session_state.user_id})
                    s.commit()
                st.success("Keywords updated!")

        with st.expander("Manage Sites", expanded=True):
            new_site = st.text_input("Add Careers URL")
            if st.button("Add Site"):
                with conn.session as s:
                    s.execute(text("INSERT INTO monitored_sites (user_id, url) VALUES (:uid, :url)"), 
                              {"uid": st.session_state.user_id, "url": new_site})
                    s.commit()
                st.rerun()

    # --- FOOTER: EXCEL REPORT ---
    st.divider()
    st.subheader("📄 Daily Excel Intelligence")
    report = conn.query("SELECT job_title, company_name, location, link, extracted_at FROM daily_excel_data WHERE user_id = :uid ORDER BY extracted_at DESC", 
                        params={"uid": st.session_state.user_id}, ttl=0)
    
    if not report.empty:
        st.dataframe(report, use_container_width=True)
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            report.to_excel(writer, index=False)
        st.download_button("📥 Download Ranked Excel", data=buffer.getvalue(), 
                           file_name=f"Ranked_Jobs_{datetime.now().strftime('%Y%m%d')}.xlsx")
