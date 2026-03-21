import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime, timedelta
from io import BytesIO
from scraper_engine import generic_scraper
from utils import extract_text_from_pdf, extract_keywords_from_cv

# --- 1. DATA PERSISTENCE HELPERS ---
DB_FILE = "user_data.json"

def load_data():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=4)

# --- 2. CONFIG ---
st.set_page_config(page_title="AI Job Monitor", layout="wide")
db = load_data()

# --- 3. USER AUTHENTICATION ---
st.sidebar.title("👤 User Portal")
username = st.sidebar.text_input("Enter Username", value="Guest").strip().lower()

if username not in db:
    db[username] = {"keywords": [], "urls": [], "last_run": None}
    save_data(db)

user_profile = db[username]

# --- 4. DASHBOARD UI ---
st.title(f"🚀 {username.capitalize()}'s Job Dashboard")

# Check for 24hr update status
if user_profile["last_run"]:
    last_run_dt = datetime.fromisoformat(user_profile["last_run"])
    next_run_dt = last_run_dt + timedelta(hours=24)
    st.sidebar.write(f"📅 **Last Scan:** {last_run_dt.strftime('%Y-%m-%d %H:%M')}")
    if datetime.now() > next_run_dt:
        st.sidebar.warning("⚠️ Scrape is over 24h old. Update recommended!")

# --- STEP 1: KEYWORDS ---
with st.expander("🎯 Edit My Search Profile", expanded=not user_profile["keywords"]):
    col1, col2 = st.columns([2, 1])
    with col1:
        new_k = st.text_input("Add Keywords (comma separated)", value=", ".join(user_profile["keywords"]))
    with col2:
        up_file = st.file_uploader("Update CV (PDF)", type=["pdf"])
    
    if st.button("Save Profile"):
        keywords = [k.strip().lower() for k in new_k.split(",") if k.strip()]
        if up_file:
            keywords.extend(extract_keywords_from_cv(extract_text_from_pdf(up_file)))
        user_profile["keywords"] = list(set(keywords))
        save_data(db)
        st.success("Profile Updated!")
        st.rerun()

# --- STEP 2: TRACKED SITES ---
st.subheader("🌐 My Monitored Sites")
new_url = st.text_input("🔗 Add New Careers URL")
if st.button("➕ Add to My List"):
    if new_url and new_url not in user_profile["urls"]:
        user_profile["urls"].append(new_url)
        save_data(db)
        st.rerun()

# List & Remove
for i, url in enumerate(user_profile["urls"]):
    c1, c2 = st.columns([9, 1])
    c1.caption(url)
    if c2.button("🗑️", key=f"del_{i}"):
        user_profile["urls"].pop(i)
        save_data(db)
        st.rerun()

st.divider()

# --- STEP 3: EXECUTION ---
if st.button("🔥 RUN 24-HOUR REFRESH", type="primary", use_container_width=True):
    if not user_profile["urls"] or not user_profile["keywords"]:
        st.error("Missing URLs or Keywords!")
    else:
        results = []
        bar = st.progress(0)
        for i, url in enumerate(user_profile["urls"]):
            df = generic_scraper(url, user_profile["keywords"])
            if not df.empty:
                df["Source"] = url
                results.append(df)
            bar.progress((i+1)/len(user_profile["urls"]))
        
        if results:
            final_df = pd.concat(results, ignore_index=True)
            st.session_state.current_results = final_df
            user_profile["last_run"] = datetime.now().isoformat()
            save_data(db)
            st.success("Scan Complete!")
            st.dataframe(final_df, use_container_width=True)
            
            # Excel Download
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                final_df.to_excel(writer, index=False)
            st.download_button("📥 Download Excel", output.getvalue(), f"{username}_jobs.xlsx")
