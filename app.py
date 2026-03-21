import streamlit as st
from scraper_engine import generic_scraper
from utils import extract_text_from_pdf, extract_keywords_from_cv

# 1. Page Configuration
st.set_page_config(page_title="AI Job Tracker", layout="wide")

# 2. Initialize Session State (This keeps your list alive)
if "tracked_sites" not in st.session_state:
    st.session_state.tracked_sites = []

st.title("🚀 AI-Powered Job Tracker")
st.markdown("Track jobs from ANY company website + match with your CV")

# --- INPUT SECTION ---
col_left, col_right = st.columns(2)

with col_left:
    new_url = st.text_input("🌐 Enter Careers Page URL", placeholder="https://company.com/jobs")
    manual_keywords = st.text_input(
        "🔑 Enter Keywords (comma separated)",
        placeholder="data scientist, quant, risk"
    )

with col_right:
    uploaded_file = st.file_uploader("📄 Upload your CV (PDF)", type=["pdf"])

# --- KEYWORD PROCESSING ---
keywords = []

if uploaded_file:
    with st.spinner("Analyzing CV..."):
        text = extract_text_from_pdf(uploaded_file)
        cv_keywords = extract_keywords_from_cv(text)
        keywords.extend(cv_keywords)
        st.info(f"📂 Extracted from CV: {', '.join(cv_keywords[:5])}...")

if manual_keywords:
    manual_list = [k.strip().lower() for k in manual_keywords.split(",") if k.strip()]
    keywords.extend(manual_list)

# Remove duplicates & clean
keywords = list(set(keywords))

# --- ADD SITE BUTTON (Refined Logic) ---
if st.button("➕ Add Site to Tracker"):
    if not new_url:
        st.error("❌ Please enter a valid URL")
    elif not keywords:
        st.error("❌ Please enter keywords or upload CV")
    else:
        st.session_state.tracked_sites.append({
            "url": new_url,
            "keywords": keywords
        })
        st.success(f"✅ Site added successfully: {new_url}")
        st.toast("Website added!", icon="🎉")
        st.rerun()

st.divider()

# --- TRACKED WEBSITES SECTION ---
st.subheader(f"📂 Tracked Websites ({len(st.session_state.tracked_sites)})")

if st.session_state.tracked_sites:
    for i, site in enumerate(st.session_state.tracked_sites):
        with st.container():
            col_info, col_action = st.columns([4, 1])
            
            with col_info:
                st.markdown(f"**🔗 {site['url']}**")
                st.caption(f"🏷️ Keywords: {', '.join(site['keywords'])}")
            
            with col_action:
                # Unique key for every button is required in loops
                if st.button("❌ Remove", key=f"remove_{i}"):
                    st.session_state.tracked_sites.pop(i)
                    st.rerun()
            st.divider()

    # --- GLOBAL RUN BUTTON ---
    if st.button("🔍 Run Tracker (Scan All Sites)"):
        all_results = []
        with st.spinner("Scraping all tracked sites..."):
            for site in st.session_state.tracked_sites:
                df = generic_scraper(site['url'], site['keywords'])
                if not df.empty:
                    all_results.append(df)
        
        if all_results:
            import pandas as pd
            final_df = pd.concat(all_results).drop_duplicates()
            st.success(f"✅ Found jobs across {len(all_results)} sites!")
            st.dataframe(final_df, use_container_width=True)
        else:
            st.warning("No matching jobs found on any tracked sites.")
else:
    st.info("No websites added yet. Add a URL and keywords above to start tracking.")

# --- DEBUG SECTION (Optional) ---
with st.expander("🛠️ Debug Session State"):
    st.write(st.session_state.tracked_sites)
