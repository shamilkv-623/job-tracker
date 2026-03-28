import PyPDF2
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import re

def extract_text_from_cv(uploaded_file):
    """Reads the uploaded PDF and returns raw text."""
    try:
        pdf_reader = PyPDF2.PdfReader(uploaded_file)
        text = ""
        for page in pdf_reader.pages:
            content = page.extract_text()
            if content:
                text += content
        return text
    except Exception as e:
        return f"Error extracting PDF: {e}"

def rank_job_match(cv_text, job_title):
    """
    Uses Cosine Similarity to compare the CV against a Job Title.
    Returns a percentage match score.
    """
    if not cv_text or not job_title:
        return 0.0
    
    # Vectorize the CV text and the Job Title
    tfidf_vectorizer = TfidfVectorizer(stop_words='english')
    try:
        tfidf_matrix = tfidf_vectorizer.fit_transform([cv_text, job_title])
        # Calculate similarity between index 0 (CV) and index 1 (Job Title)
        match_score = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])
        return round(float(match_score[0][0]) * 100, 1)
    except Exception:
        return 0.0

def get_clean_company_name(url):
    """Extracts the company name from a URL for the Excel report."""
    try:
        domain = url.split("//")[-1].split("/")[0]
        parts = domain.split('.')
        # Handles 'usijobs.deloitte.com' -> 'Deloitte'
        name = parts[1] if len(parts) > 2 else parts[0]
        return name.replace("fa", "JPMC").capitalize()
    except:
        return "Company"
