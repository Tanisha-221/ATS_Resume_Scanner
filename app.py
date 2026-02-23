from flask import Flask, render_template, request
import re
import pdfplumber
from docx import Document
from io import BytesIO
import yaml

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5 MB

# ---------------- CONFIG ----------------
ALLOWED_EXTENSIONS = {"pdf", "docx"}

# ---------------- LOAD YAML ----------------
with open("roles_skills.yaml", "r") as f:
    YAML_DATA = yaml.safe_load(f)

ALL_SKILLS = set(YAML_DATA.get("all_skills", []))
ROLE_SKILLS = YAML_DATA.get("roles", {})

# ---------------- FILE HELPERS ----------------
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def extract_pdf(file_stream):
    text = ""
    with pdfplumber.open(file_stream) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text


def extract_docx(file_stream):
    doc = Document(file_stream)
    return "\n".join(p.text for p in doc.paragraphs)


def extract_resume_text(file):
    content = BytesIO(file.read())
    if file.filename.lower().endswith(".pdf"):
        return extract_pdf(content)
    if file.filename.lower().endswith(".docx"):
        return extract_docx(content)
    return ""

# ---------------- NLP HELPERS ----------------
def normalize(text):
    return re.sub(r"\s+", " ", text.lower())


def extract_skills(text, skill_set):
    text = normalize(text)
    found = set()
    for skill in skill_set:
        if re.search(rf"\b{re.escape(skill.lower())}\b", text):
            found.add(skill)
    return found


def extract_candidate_details(text):
    details = {}

    email = re.search(r"[\w.-]+@[\w.-]+\.[a-zA-Z]{2,}", text)
    details["email"] = email.group() if email else "Not Found"

    phone = re.search(r"(\+91[-\s]?)?\d{10}", text)
    details["phone"] = phone.group() if phone else "Not Found"

    lines = [l.strip() for l in text.split("\n") if l.strip()]
    details["name"] = lines[0] if lines else "Not Found"

    exp = re.search(r"(\d+)\+?\s*years?", text.lower())
    details["experience"] = exp.group() if exp else "Not Mentioned"

    edu = re.search(r"(bachelor|master|phd|btech|mtech|mba)", text.lower())
    details["education"] = edu.group().upper() if edu else "Not Mentioned"

    return details


def extract_strengths(text):
    text = text.lower()
    strengths = []

    if any(x in text for x in ["certified", "certificate", "coursera", "udemy", "nptel"]):
        strengths.append("Professional Certifications")

    if "internship" in text:
        strengths.append("Internship Experience")

    if "project" in text:
        strengths.append("Hands-on Projects")

    return strengths

# ---------------- ATS SCORE ----------------
def calculate_score(resume_text, job_role=None, jd_text=None):
    resume_skills = extract_skills(resume_text, ALL_SKILLS)

    # Priority 1: Job Role
    if job_role and job_role in ROLE_SKILLS:
        required_skills = set(ROLE_SKILLS[job_role])

    # Priority 2: Job Description
    elif jd_text:
        required_skills = extract_skills(jd_text, ALL_SKILLS)

    else:
        return 0, [], []

    matched = resume_skills & required_skills
    missed = required_skills - resume_skills

    score = round((len(matched) / len(required_skills)) * 100, 2) if required_skills else 0

    return score, sorted(matched), sorted(missed)

# ---------------- ROUTES ----------------
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        role_type = request.form.get("role")  # FIXED
        job_role = request.form.get("job_role")
        jd_text = request.form.get("jd") or request.form.get("jd_text")

        results = []

        # -------- JOB SEEKER --------
        if role_type == "job_seeker":
            resumes = request.files.getlist("resumes")

            for file in resumes:
                if not allowed_file(file.filename):
                    continue

                resume_text = extract_resume_text(file)

                candidate = extract_candidate_details(resume_text)
                candidate["strengths"] = extract_strengths(resume_text)

                score, matched, missed = calculate_score(
                    resume_text,
                    job_role=job_role,
                    jd_text=jd_text
                )

                candidate.update({
                    "resume": file.filename,
                    "score": score,
                    "skills": matched,
                    "missed": missed
                })

                results.append(candidate)

            return render_template("job_seeker_results.html", results=results)

        # -------- HIRING TEAM --------
        if role_type == "hiring_team":
            resumes = request.files.getlist("job_seekers")

            for file in resumes:
                if not allowed_file(file.filename):
                    continue

                resume_text = extract_resume_text(file)

                candidate = extract_candidate_details(resume_text)
                candidate["strengths"] = extract_strengths(resume_text)

                score, matched, missed = calculate_score(
                    resume_text,
                    job_role=job_role,
                    jd_text=jd_text
                )

                candidate.update({
                    "resume": file.filename,
                    "score": score,
                    "skills": matched,
                    "missed": missed
                })

                results.append(candidate)

            results.sort(key=lambda x: x["score"], reverse=True)
            return render_template("hiring_team_results.html", results=results)

    return render_template("index.html")


if __name__ == "__main__":
    app.run(debug=True)