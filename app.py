from flask import Flask, render_template, request
import re
from pdfminer.high_level import extract_text
from docx import Document
import os
from tempfile import NamedTemporaryFile

app = Flask(__name__)

#--------TEXT EXTRACTION---------------
def extract_resume_text(file):
    # Handling PDF files
    if file.filename.endswith(".pdf"):
        with NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
            file.save(temp_file.name)
            return extract_text(temp_file.name)
    
    # Handling DOCX files
    elif file.filename.endswith(".docx"):
        doc = Document(file)
        return "\n".join(p.text for p in doc.paragraphs)
    
    return ""

#--------Basic Cleaning----------------
def preprocess(text):
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s]', ' ', text)
    tokens = text.split()
    return set(tokens)

#---------INFO EXTRACTION--------------
def extract_email(text):
    match = re.search(r'[\w\.-]+@[w\.-]+', text)
    return match.group() if match else "Not Found"

def extract_phone(text):
    match = re.search(r'\b\d{10}\b', text)
    return match.group() if match else "Not Found"

#---------ATS SCORING----------------
def calculate_score(jd_text, resume_text):
    jd_toxens = preprocess(jd_text)
    resume_tokens = preprocess(resume_text)

    if not jd_toxens:
        return 0, []
    
    matched = jd_toxens.intersection(resume_tokens)
    score = round((len(matched) / len(jd_toxens)) * 100, 2)

    return score, list(matched)

#------------ROUTE---------------------
@app.route("/", methods=["GET", "POST"])
def index():
    results = []

    if request.method == "POST":
        resumes = request.files.getlist("resumes")
        jd_text = request.form.get("jd")

        for file in resumes:
            if file.filename.endswith((".pdf", ".docx")):
                resume_text = extract_resume_text(file)
                score, matched_skills = calculate_score(jd_text, resume_text)
                result = {
                    "name": file.filename,
                    "email": extract_email(resume_text),
                    "phone": extract_phone(resume_text),
                    "score": score,
                    "skills": matched_skills
                }

                results.append(result)

            results.sort(key=lambda x: x["score"], reverse=True)

        return render_template("index.html", results=results)
    
    return render_template("index.html", results=results)
    
if __name__ == "__main__":
    app.run(debug=True)