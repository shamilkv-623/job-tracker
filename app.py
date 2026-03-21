import streamlit as st
import pandas as pd
from scraper_engine import generic_scraper
from utils import extract_text_from_pdf, extract_keywords_from_cv

st.set_page_config(page_title="AI Job Tracker", layout="wide")

st.title("🚀 AI-Powered Job Tracker")
st.markdown("Track jobs from MULTIPLE company websites + match with your CV")

# -------------------------------
# SESSION STATE (store sites)
# -------------------------------
if "tracked_sites" not in st.session_state:
    st.session_state.tracked_sites = []

# -------------------------------
# INPUT SECTION
# -------------------------------
st.subheader("➕ Add Website to Track")

new_url = st.text_input("🌐 Enter Careers Page URL")
manual_keywords = st.text_input(
    "🔑 Enter Keywords (comma separated)",
    placeholder="data scientist, quant, risk"
)

uploaded_file = st.file_uploader("📄 Upload your CV (PDF)", type=["pdf"])

keywords = []

# -------------------------------
# PROCESS CV
# -------------------------------
if uploaded_file:
    text = extract_text_from_pdf(uploaded_file)
    cv_keywords = extract_keywords_from_cv(text)

    st.subheader("📌 Extracted Keywords from CV")
    st.write(cv_keywords)

    keywords.extend(cv_keywords)

# -------------------------------
# MANUAL KEYWORDS
# -------------------------------
if manual_keywords:
    manual_list = [k.strip().lower() for k in manual_keywords.split(",")]
    keywords.extend(manual_list)

# Remove duplicates
keywords = list(set(keywords))

# -------------------------------
# ADD SITE BUTTON
# -------------------------------
if st.button("➕ Add Site"):
    if new_url and keywords:
        st.session_state.tracked_sites.append({
            "url": new_url,
            "keywords": keywords
        })
        st.success("✅ Site added successfully!")
    else:
        st.warning("Please enter URL and keywords")

# -------------------------------
# SHOW TRACKED SITES
# -------------------------------
st.subheader("📂 Tracked Websites")

if st.session_state.tracked_sites:
    for i, site in enumerate(st.session_state.tracked_sites):
        col1, col2 = st.columns([4, 1])

        with col1:
            st.write(f"{i+1}. {site['url']}")
            st.write(f"Keywords: {site['keywords']}")

        with col2:
            if st.button("❌ Remove", key=f"remove_{i}"):
                st.session_state.tracked_sites.pop(i)
                st.rerun()
else:
    st.info("No websites added yet.")

# -------------------------------
# RUN ALL TRACKING
# -------------------------------
st.subheader("🔍 Run Monitoring")

if st.button("🚀 Run for All Websites"):
    if st.session_state.tracked_sites:
        all_results = []

        with st.spinner("Scraping all websites..."):
            for site in st.session_state.tracked_sites:
                df = generic_scraper(site["url"], site["keywords"])

                if not df.empty and "Error" not in df.columns:
                    all_results.append(df)

        if all_results:
            final_df = pd.concat(all_results, ignore_index=True)

            st.success("✅ Jobs Found!")
            st.dataframe(final_df, use_container_width=True)

            csv = final_df.to_csv(index=False).encode("utf-8")

            st.download_button(
                "📥 Download All Results",
                csv,
                "all_jobs.csv",
                "text/csv"
            )
        else:
            st.warning("No jobs found across all sites")
    else:
        st.warning("Please add at least one website")
