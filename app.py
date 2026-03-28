import streamlit as st
import pandas as pd
import bcrypt
import requests
import io
from bs4 import BeautifulSoup
from sqlalchemy import text
from urllib.parse import urljoin

# ---------------- DB HELPERS ----------------
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

# ---------------- MAIN DASHBOARD ----------------
# (Inside your 'else' block for logged_in users)

st.title("📊 Career Monitor Dashboard")
col1, col2 = st.columns([2, 1])

with col2:
    st.subheader("👤 Your Profile")
    
    # Keyword Management
    curr_keys = st.session_state.user_data.get('keywords', "")
    with st.expander("Edit Keywords"):
        new_keys = st.text_area("Keywords (comma separated)", value=curr_keys)
        if st.button("Save Keywords"):
            update_user_settings(st.session_state.user_id, new_keys, "")
            st.success("Keywords updated!")

    st.divider()
    st.subheader("🔗 Monitored Sites")
    
    # ADD SITE BUTTON
    new_url = st.text_input("Add Company Careers URL")
    if st.button("➕ Add Site"):
        if new_url:
            if add_monitored_site(st.session_state.user_id, new_url):
                st.success("Site added to monitoring list!")
                st.rerun()

    # DISPLAY LIST OF SITES
    sites_df = get_monitored_sites(st.session_state.user_id)
    if not sites_df.empty:
        for url in sites_df['url']:
            st.caption(f"📍 {url}")
    else:
        st.write("No sites added yet.")

with col1:
    st.subheader("🔎 Live Job Scanner")
    
    if not sites_df.empty:
        # Dropdown to select which of your saved sites to scan manually
        target_to_scan = st.selectbox("Select site to scan", options=sites_df['url'].tolist())
        
        if st.button("Manual Scan Now"):
            with st.spinner(f"Scanning {target_to_scan}..."):
                # Use your existing quick_scrape function
                found_jobs = quick_scrape(target_to_scan, curr_keys)
                if found_jobs:
                    st.markdown("### Relevant Jobs Found:")
                    for job in found_jobs:
                        st.markdown(f"- **{job['title']}** | [Open Link]({job['link']})")
                else:
                    st.info("No matches found for your keywords on this page.")
    else:
        st.warning("Please add a site in the profile section to start scanning.")

st.divider()

# (Keep your existing Daily Excel Intelligence section here)
# It will now work for ALL sites added above when the 24h cron runs.
