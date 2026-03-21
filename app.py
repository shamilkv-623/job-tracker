import streamlit as st
from scraper_engine import generic_scraper
from utils import extract_text_from_pdf, extract_keywords_from_cv

st.set_page_config(page_title="AI Job Tracker", layout="wide")

st.title("🚀 AI-Powered Job Tracker")

st.markdown("Track jobs from ANY company website + match with your CV")

# --- INPUT SECTION ---
url = st.text_input("🌐 Enter Careers Page URL")

manual_keywords = st.text_input(
    "🔑 Enter Keywords (comma separated)",
    placeholder="data scientist, quant, risk"
)

uploaded_file = st.file_uploader("📄 Upload your CV (PDF)", type=["pdf"])

keywords = []

# --- PROCESS CV ---
if uploaded_file:
    text = extract_text_from_pdf(uploaded_file)
    cv_keywords = extract_keywords_from_cv(text)

    st.subheader("📌 Extracted Keywords from CV")
    st.write(cv_keywords)

    keywords.extend(cv_keywords)

# --- MANUAL KEYWORDS ---
if manual_keywords:
    manual_list = [k.strip().lower() for k in manual_keywords.split(",")]
    keywords.extend(manual_list)

# Remove duplicates
keywords = list(set(keywords))

# --- RUN SCRAPER ---
if st.button("🔍 Find Jobs"):
    if url and keywords:
        with st.spinner("Scraping jobs..."):
            df = generic_scraper(url, keywords)

        st.success("✅ Done!")

        if not df.empty:
            st.dataframe(df, use_container_width=True)

            csv = df.to_csv(index=False).encode("utf-8")

            st.download_button(
                "📥 Download Results",
                csv,
                "jobs.csv",
                "text/csv"
            )
        else:
            st.warning("No jobs found")
    else:
        st.warning("Please provide URL and keywords or CV")
