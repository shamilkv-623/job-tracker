import streamlit as st
import pandas as pd
from scraper_engine import generic_scraper
from utils import extract_text_from_pdf, extract_keywords_from_cv

# --- 1. CONFIG & SESSION STATE ---
st.set_page_config(page_title="AI Job Tracker", layout="wide", page_icon="🚀")

# This keeps your website list alive even when you add new ones
if "target_sites" not in st.session_state:
    st.session_state.target_sites = []

st.title("🚀 AI-Powered Job Tracker")

# --- 2. STEP 1: GLOBAL KEYWORDS ---
st.subheader("🎯 Step 1: Define Your Master Keywords")
st.info("These keywords will apply to EVERY website you add below.")

col_k1, col_k2 = st.columns([2, 1])
with col_k1:
    manual_keywords = st.text_input(
        "🔑 Master Keywords (comma separated)",
        placeholder="e.g. quant, data scientist, risk",
        key="master_k_input"
    )
with col_k2:
    uploaded_file = st.file_uploader("📄 Upload CV (PDF)", type=["pdf"])

# Consolidate Keywords
master_keywords = []
if uploaded_file:
    with st.spinner("Reading CV..."):
        text = extract_text_from_pdf(uploaded_file)
        master_keywords.extend(extract_keywords_from_cv(text))

if manual_keywords:
    manual_list = [k.strip().lower() for k in manual_keywords.split(",") if k.strip()]
    master_keywords.extend(manual_list)

master_keywords = list(set(master_keywords)) # Deduplicate

if master_keywords:
    st.success(f"✅ **Targeting:** {', '.join(master_keywords)}")

st.divider()

# --- 3. STEP 2: BUILD YOUR LIST ---
st.subheader("🌐 Step 2: Build Your Target List")

col_url, col_btn = st.columns([4, 1])
with col_url:
    new_url = st.text_input("🔗 Enter Careers Page URL", placeholder="https://company.com/careers")
with col_btn:
    st.write(" ") # Padding
    if st.button("➕ Add Website", use_container_width=True):
        if new_url:
            if new_url not in st.session_state.target_sites:
                st.session_state.target_sites.append(new_url)
                st.toast(f"Added {new_url}!", icon="📍")
                st.rerun()
            else:
                st.warning("This URL is already in your list.")
        else:
            st.error("Please enter a URL first.")

# --- DISPLAY THE LIST ---
if st.session_state.target_sites:
    st.write(f"**Your Websites ({len(st.session_state.target_sites)}):**")
    for i, site in enumerate(st.session_state.target_sites):
        c1, c2 = st.columns([9, 1])
        c1.caption(f"{i+1}. {site}")
        if c2.button("🗑️", key=f"del_{i}"):
            st.session_state.target_sites.pop(i)
            st.rerun()
else:
    st.info("Your list is empty. Add a URL above.")

st.divider()

# --- 4. STEP 3: EXECUTION ---
st.subheader("🚀 Step 3: Run Monitoring")

if st.button("🔥 START SCRAPING ALL SITES", type="primary", use_container_width=True):
    if not st.session_state.target_sites:
        st.error("❌ Add at least one website in Step 2.")
    elif not master_keywords:
        st.error("❌ No keywords detected in Step 1.")
    else:
        all_results = []
        progress_bar = st.progress(0)
        status = st.empty()
        
        for i, url in enumerate(st.session_state.target_sites):
            status.info(f"Scanning ({i+1}/{len(st.session_state.target_sites)}): {url}...")
            
            try:
                # Scrape using the MASTER KEYWORDS from Step 1
                df = generic_scraper(url, master_keywords)
                if not df.empty and "Error" not in df.columns:
                    df["Source URL"] = url
                    all_results.append(df)
            except Exception as e:
                st.error(f"Error on {url}: {e}")
            
            progress_bar.progress((i + 1) / len(st.session_state.target_sites))
        
        status.empty()

        if all_results:
            final_df = pd.concat(all_results, ignore_index=True).drop_duplicates()
            st.success(f"🎊 Done! Found {len(final_df)} jobs matching your keywords.")
            st.dataframe(final_df, use_container_width=True)
            
            csv = final_df.to_csv(index=False).encode("utf-8")
            st.download_button("📥 Download Results (CSV)", csv, "jobs_report.csv", "text/csv")
        else:
            st.warning("No matching jobs found across all sites.")

# --- FOOTER ---
with st.expander("🛠️ Debug Information"):
    st.write("Keywords being used:", master_keywords)
    st.write("Site List:", st.session_state.target_sites)
