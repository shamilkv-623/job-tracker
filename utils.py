import PyPDF2

def extract_text_from_pdf(file):
    text = ""
    pdf_reader = PyPDF2.PdfReader(file)

    for page in pdf_reader.pages:
        text += page.extract_text() or ""

    return text

def extract_keywords_from_cv(text):
    # simple keyword extraction (can upgrade later)
    words = text.lower().split()

    keywords = list(set([
        w for w in words if len(w) > 4
    ]))

    return keywords[:15]  # limit
