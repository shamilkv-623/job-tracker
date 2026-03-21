import streamlit as st
import pandas as pd
from scraper_engine import generic_scraper
from utils import extract_text_from_pdf, extract_keywords_from_cv

# --- 1. INITIAL CONFIG ---
st.set_page_config(page_title="AI Job Tracker", layout="wide", page_icon="🚀")

st.title("🚀 AI-Powered Job Tracker")
st.markdown("Set your profile once, paste your target URLs, and run the scan.")

# --- 2. THE MASTER KEYWORDS (Step 1) ---
st.subheader("🎯 Step 1: Define Your Search Profile")
st.info("These keywords will be used to filter jobs across ALL websites you provide below.")

col_key1, col_key2 = st.columns([2, 1])

with col_key1:
    manual_keywords = st.text_input(
        "🔑 Enter Keywords (comma separated)",
        placeholder="e.g. data scientist, quant, python, risk",
        help="Type your keywords and press Enter."
    )

with col_key2:
    uploaded_file = st.file_uploader("📄 Or Upload CV (PDF)", type=["pdf"])

# Consolidate Keywords into a single master list
master_keywords = []

if uploaded_file:
    with st.spinner("Analyzing CV..."):
        text = extract_text_from_pdf(uploaded_file)
        cv_keywords = extract_keywords_from_cv(text)
        master_keywords.extend(cv_keywords)

if manual_keywords:
    manual_list = [k.strip().lower() for k in manual_keywords.split(",") if k.strip()]
    master_keywords.extend(manual_list)

# Clean and remove duplicates
master_keywords = list(set(master_keywords))

if master_keywords:
    st.success(f"**Targeting {len(master_keywords)} Keywords:** {', '.join(master_keywords)}")
else:
    st.warning("⚠️ No keywords detected yet. Please type some or upload your CV.")

st.divider()

# --- 3. THE TARGET LIST (Step 2) ---
st.subheader("🌐 Step 2: List Careers Pages")
urls_input = st.text_area(
    "Paste one Careers Page URL per line:",
    placeholder="https://company-a.com/jobs\nhttps://company-b.com/careers",
    height=150
)

# Parse the text area into a clean list
url_list = [url.strip() for url in urls_input.split("\n") if url.strip()]

if url_list:
    st.caption(f"✅ {len(url_list)} websites ready for scanning.")

st.divider()

# --- 4. EXECUTION (Step 3) ---
st.subheader("🚀 Step 3: Run Execution")

# Big Action Button
if st.button("🔥 START MULTI-SITE SCAN", type="primary", use_container_width=True):
    if not url_list:
        st.error("❌ Please provide at least one URL in Step 2.")
    elif not master_keywords:
        st.error("❌ Please provide keywords or a CV in Step 1.")
    else:
        all_results = []
        
        # UI Feedback elements
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, url in enumerate(url_list):
            status_text.info(f"Scanning ({i+1}/{len(url_list)}): {url}...")
            
            # Run the scraper using the master keyword list
            try:
                df = generic_scraper(url, master_keywords)
                
                if not df.empty and "Error" not in df.columns:
                    # Add a column so we know which site the job came from
                    df["Source URL"] = url
                    all_results.append(df)
            except Exception as e:
                st.error(f"Error scanning {url}: {e}")
            
            # Update progress
            progress_bar.progress((i + 1) / len(url_list))
        
        status_text.empty() # Clear the status when finished

        # --- FINAL RESULTS ---
        if all_results:
            final_df = pd.concat(all_results, ignore_index=True).drop_duplicates()
            st.success(f"🎊 Finished! Found {len(final_df)} matching jobs across your list.")
            
            # Display Interactive Table
            st.dataframe(final_df, use_container_width=True)

            # Download CSV
            csv_data = final_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="📥 Download Master Job List (CSV)",
                data=csv_data,
                file_name="scraped_jobs_report.csv",
                mime="text/csv"
            )
        else:
            st.warning("No matching jobs were found on any of the provided sites.")

# --- FOOTER / DEBUG ---
with st.expander("🛠️ System Metadata"):
    st.write("Current Master Keyword List:", master_keywords)
    st.write("Detected URLs:", url_list)
