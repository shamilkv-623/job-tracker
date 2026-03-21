import streamlit as st
import pandas as pd
from scraper_engine import generic_scraper
from utils import extract_text_from_pdf, extract_keywords_from_cv

# --- PAGE SETUP ---
st.set_page_config(page_title="AI Job Tracker", layout="wide")

st.title("🚀 AI-Powered Job Tracker")
st.markdown("Track jobs from MULTIPLE company websites + match with your CV")

# --- SESSION STATE ---
if "tracked_sites" not in st.session_state:
    st.session_state.tracked_sites = []

# --- INPUT SECTION ---
st.subheader("➕ Add Website to Track")

col_inputs, col_upload = st.columns([2, 1])

with col_inputs:
    new_url = st.text_input("🌐 Enter Careers Page URL", placeholder="https://company.com/careers")
    manual_keywords = st.text_input(
        "🔑 Enter Keywords (comma separated)",
        placeholder="data scientist, quant, risk",
        help="Type keywords and press Enter before clicking 'Add Site'"
    )

with col_upload:
    uploaded_file = st.file_uploader("📄 Upload your CV (PDF) to auto-extract", type=["pdf"])

# --- CONSOLIDATE KEYWORDS ---
keywords = []

# 1. Process CV Keywords
if uploaded_file:
    with st.spinner("Extracting from CV..."):
        text = extract_text_from_pdf(uploaded_file)
        cv_keywords = extract_keywords_from_cv(text)
        keywords.extend(cv_keywords)
        if cv_keywords:
            st.info(f"✅ Found {len(cv_keywords)} keywords in CV")

# 2. Process Manual Keywords
if manual_keywords:
    manual_list = [k.strip().lower() for k in manual_keywords.split(",") if k.strip()]
    keywords.extend(manual_list)

# 3. Clean and deduplicate
keywords = list(set(keywords))

# --- ADD SITE LOGIC ---
if st.button("➕ Add Site to Tracker", use_container_width=True):
    if not new_url:
        st.error("❌ Please enter a Careers Page URL")
    elif not keywords:
        # This handles the error you saw in the screenshot
        st.error("❌ No keywords found. Please type manual keywords (and press Enter) or upload a CV.")
    else:
        # Add to state
        st.session_state.tracked_sites.append({
            "url": new_url,
            "keywords": keywords
        })
        st.success(f"✅ Added {new_url} to your list!")
        st.toast("Site added!", icon="🎉")
        # Rerun to refresh the list and clear inputs
        st.rerun()

st.divider()

# --- TRACKED WEBSITES LIST ---
st.subheader(f"📂 Tracked Websites ({len(st.session_state.tracked_sites)})")

if st.session_state.tracked_sites:
    for i, site in enumerate(st.session_state.tracked_sites):
        with st.expander(f"📍 {site['url']}", expanded=True):
            c1, c2 = st.columns([5, 1])
            with c1:
                st.write(f"**Keywords:** {', '.join(site['keywords'])}")
            with c2:
                if st.button("❌ Remove", key=f"remove_{i}"):
                    st.session_state.tracked_sites.pop(i)
                    st.rerun()

    # --- RUN MONITORING ---
    st.subheader("🔍 Run Monitoring")
    if st.button("🚀 Run for All Websites", type="primary", use_container_width=True):
        all_results = []

        progress_bar = st.progress(0)
        num_sites = len(st.session_state.tracked_sites)

        for i, site in enumerate(st.session_state.tracked_sites):
            st.write(f"Scanning: {site['url']}...")
            df = generic_scraper(site["url"], site["keywords"])

            if not df.empty and "Error" not in df.columns:
                all_results.append(df)
            
            progress_bar.progress((i + 1) / num_sites)

        if all_results:
            final_df = pd.concat(all_results, ignore_index=True).drop_duplicates()
            st.success(f"✅ Done! Found {len(final_df)} matching jobs.")
            st.dataframe(final_df, use_container_width=True)

            csv = final_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                "📥 Download All Results",
                csv,
                "tracked_jobs.csv",
                "text/csv"
            )
        else:
            st.warning("No jobs found matching your criteria across these sites.")
else:
    st.info("No websites added yet. Use the form above to add your first company.")

# --- DEBUG (Hidden by default) ---
with st.expander("🛠️ System Debug"):
    st.write("Current Keywords List:", keywords)
    st.write("Session State:", st.session_state.tracked_sites)
