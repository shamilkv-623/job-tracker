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

# ---------------- CONFIG ----------------
st.set_page_config(page_title="Horizon AI | Career Monitor", layout="wide", page_icon="🚀")

# ---------------- DB CONNECTION ----------------
@st.cache_resource
def get_connection():
    return st.connection("postgresql", type="sql")

conn = get_connection()

# ---------------- HELPERS ----------------
def extract_company_from_url(url):
    """Extracts a clean company name from the URL."""
    domain = url.split("//")[-1].split("/")[0]
    parts = domain.split('.')
    # Returns 'Deloitte' from 'usijobs.deloitte.com'
    name = parts[1] if len(parts) > 2 else parts[0]
    return name.capitalize()

def extract_location(text_val):
    """Attempts to find a location (e.g., Hyderabad, Mumbai, USA) in the job title."""
    # Look for common city names or patterns after a hyphen
    match = re.search(r'-\s*([a-zA-Z\s]+)$', text_val)
    if match:
        return match.group(1).strip()
    return "Remote/Global"

# ---------------- DB FUNCTIONS ----------------
def get_monitored_sites(user_id):
    return conn.query("SELECT id, url FROM monitored_sites WHERE user_id = :uid", params={"uid": user_id}, ttl=0)

def add_monitored_site(user_id, url):
    try:
        with conn.session as s:
            s.execute(text("INSERT INTO monitored_sites (user_id, url) VALUES (:uid, :url)"), {"uid": user_id, "url": url})
            s.commit()
        return True
    except Exception as e:
        st.error(f"Error: {e}")
        return False

# ---------------- SCRAPER ----------------
def quick_scrape(url: str, keywords_str: str, location_filter: str):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")
        
        keyword_list = [k.strip().lower() for k in keywords_str.split(",")] if keywords_str else []
        loc_filter = location_filter.lower().strip()
        jobs = []

        company_name = extract_company_from_url(url)

        for a in soup.find_all("a"):
            text_val = a.get_text(strip=True)
            href = a.get("href", "")
            
            # Check Keywords AND Location Filter
            matches_key = any(k in text_val.lower() for k in keyword_list) if keyword_list else True
            matches_loc = loc_filter in text_val.lower() if loc_filter else True
            
            if matches_key and matches_loc and len(text_val) > 5:
                detected_loc = extract_location(text_val)
                jobs.append({
                    "title": text_val,
                    "link": urljoin(url, href),
                    "company": company_name,
                    "location": detected_loc
                })

        unique_jobs = {j['title']: j for j in jobs}.values()
        return list(unique_jobs)
    except Exception as e:
        return []

# ---------------- MAIN DASHBOARD ----------------
if not st.session_state.get("logged_in"):
    st.title("Please Login") # Simplified for space
else:
    st.title("📊 Career Monitor Dashboard")
    col1, col2 = st.columns([2, 1])

    with col2:
        st.subheader("👤 Your Profile")
        sites_df = get_monitored_sites(st.session_state.user_id)
        
        with st.expander("Add New Site"):
            new_site = st.text_input("Careers URL")
            if st.button("➕ Add Site"):
                if add_monitored_site(st.session_state.user_id, new_site):
                    st.rerun()
        
        for index, row in sites_df.iterrows():
            st.caption(f"📍 {row['url']}")

    with col1:
        st.subheader("🔎 Live Job Scanner")
        
        # --- NEW LOCATION FILTER ---
        loc_input = st.text_input("🌍 Filter by Country or City (e.g. Hyderabad, USA)", placeholder="Leave blank for all")
        
        if not sites_df.empty:
            all_urls = sites_df['url'].tolist()
            selected_url = st.selectbox("Select site", options=["SCAN ALL"] + all_urls)
            
            if st.button("Run Scan"):
                urls_to_process = all_urls if selected_url == "SCAN ALL" else [selected_url]
                new_matches = []

                for url in urls_to_process:
                    found = quick_scrape(url, st.session_state.user_data.get('keywords', ""), loc_input)
                    if found:
                        st.write(f"**Results for {extract_company_from_url(url)}:**")
                        for job in found:
                            st.markdown(f"- **{job['title']}** | {job['location']} [Link]({job['link']})")
                            new_matches.append(job)

                if new_matches:
                    with conn.session as s:
                        for job in new_matches:
                            s.execute(
                                text("INSERT INTO daily_excel_data (user_id, job_title, company_name, location, link) VALUES (:uid, :title, :comp, :loc, :link)"),
                                {"uid": st.session_state.user_id, "title": job['title'], "comp": job['company'], "loc": job['location'], "link": job['link']}
                            )
                        s.commit()
                    st.success("Syncing to Excel...")
                    st.rerun()

    # --- EXCEL DOWNLOAD SECTION ---
    st.divider()
    st.subheader("📄 Excel Job Tracker")
    report_data = conn.query("SELECT job_title, company_name, location, link, extracted_at FROM daily_excel_data WHERE user_id = :uid", params={"uid": st.session_state.user_id}, ttl=0)
    
    if not report_data.empty:
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            report_data.to_excel(writer, index=False)
        st.download_button("📥 Download Excel Report", data=buffer.getvalue(), file_name="Job_Tracker.xlsx", use_container_width=True)
