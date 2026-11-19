import sys
from pathlib import Path
from uuid import uuid4
import re
import html
import textwrap
from typing import Optional, List
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.paths import safe_path, output_dir, PathNotAllowed

app = FastAPI(title="Resume Runtime")
OUTPUTS_DIR = output_dir(Path(__file__).resolve().parent)


class ResumeReq(BaseModel):
    resume_text: Optional[str] = None
    job_description: Optional[str] = None
    resume_data: Optional[str] = None
    projects_data: Optional[str] = None


def check_paths_in_req(req: ResumeReq):
    for val in [req.resume_text, req.job_description, req.resume_data, req.projects_data]:
        if val and isinstance(val, str) and val.strip().startswith("/"):
            try:
                safe_path(val.strip())
            except PathNotAllowed as e:
                raise HTTPException(status_code=403, detail=str(e))
            except FileNotFoundError as e:
                raise HTTPException(status_code=404, detail=str(e))


SKILLS = [
    "Python", "Java", "JavaScript", "TypeScript", "Go", "Rust", "C++", "SQL",
    "PostgreSQL", "MySQL", "MongoDB", "Redis", "Docker", "Kubernetes", "AWS",
    "GCP", "Azure", "Terraform", "Linux", "Git", "FastAPI", "Django", "Flask",
    "React", "Node.js", "GraphQL", "REST", "Kafka", "Spark", "Airflow",
    "TensorFlow", "PyTorch", "Machine Learning", "Algorand", "Blockchain",
    "Solidity", "CI/CD", "Agile", "HTML", "CSS", "C#", "PHP", "Ruby", "Swift",
    "Kotlin", "Scala", "R", "Shell", "Bash", "Ansible", "Jenkins", "OpenSearch",
    "Elasticsearch", "Pandas", "NumPy", "Scikit-Learn", "Keras", "Next.js",
    "Vue", "Angular", "Svelte", "Microservices", "DevOps"
]

WEAK_PHRASES = [
    "responsible for", "helped with", "assisted with", "worked on",
    "duties included", "involved in"
]

ACTION_VERBS = [
    "built", "led", "designed", "architected", "shipped", "increased",
    "reduced", "launched", "automated", "optimized", "implemented", "created"
]


def _skills(text: str) -> List[str]:
    if not text:
        return []
    matches = []
    for skill in SKILLS:
        pat = r'(?<![A-Za-z0-9])' + re.escape(skill) + r'(?![A-Za-z0-9])'
        for m in re.finditer(pat, text, re.IGNORECASE):
            matches.append((m.start(), skill))
    matches.sort(key=lambda x: x[0])
    seen = set()
    res = []
    for _, s in matches:
        if s not in seen:
            seen.add(s)
            res.append(s)
    return res


def _name(text: str) -> str:
    if not text:
        return "Candidate"
    for line in text.splitlines():
        line = line.strip()
        if line:
            return line
    return "Candidate"


@app.post("/resume_score")
def resume_score(req: ResumeReq):
    check_paths_in_req(req)
    text = req.resume_text or ""
    words = text.split()
    word_count = len(words)
    if word_count >= 150:
        length_pts = 20
    elif word_count >= 60:
        length_pts = 12
    else:
        length_pts = 5

    sections = ["experience", "education", "skills", "projects", "summary"]
    found_sections = []
    for sec in sections:
        if re.search(r'\b' + re.escape(sec) + r'\b', text, re.IGNORECASE):
            found_sections.append(sec)
    sections_pts = min(20, len(found_sections) * 5)

    quant_matches = re.findall(r"\d+%|\$\d|\d+x\b|\d{2,}", text)
    quant_pts = min(20, len(quant_matches) * 5)

    found_verbs = []
    for verb in ACTION_VERBS:
        if re.search(r'\b' + re.escape(verb) + r'\b', text, re.IGNORECASE):
            found_verbs.append(verb)
    action_pts = min(15, len(found_verbs) * 3)

    found_skills = _skills(text)
    skills_pts = min(20, len(found_skills) * 2)

    found_weak = []
    for phrase in WEAK_PHRASES:
        if re.search(r'\b' + re.escape(phrase) + r'\b', text, re.IGNORECASE):
            found_weak.append(phrase)
    weak_penalty = len(found_weak) * 5

    raw_score = length_pts + sections_pts + quant_pts + action_pts + skills_pts - weak_penalty
    total_score = max(0, min(100, raw_score))

    tips = []
    if length_pts < 20:
        tips.append("Expand on your achievements and responsibilities to reach at least 150 words.")
    if sections_pts < 20:
        missing_sec = [s for s in sections if s not in found_sections]
        tips.append(f"Add missing core sections: {', '.join(missing_sec)}.")
    if quant_pts < 15:
        tips.append("Quantify your impact using metrics, percentages, and performance gains.")
    if found_weak:
        tips.append(f"Eliminate passive phrasing such as '{found_weak[0]}'.")

    output_lines = [
        f"Resume Score: {total_score}/100",
        f"- Length: {length_pts}/20 points ({word_count} words)",
        f"- Sections: {sections_pts}/20 points ({len(found_sections)}/5 core sections)",
        f"- Quantified Results: {quant_pts}/20 points ({len(quant_matches)} metrics)",
        f"- Action Verbs: {action_pts}/15 points ({len(found_verbs)} verbs)",
        f"- Technical Skills: {skills_pts}/20 points ({len(found_skills)} skills)",
        f"- Weak Phrases Penalty: -{weak_penalty} points ({len(found_weak)} weak phrases)",
    ]
    if tips:
        output_lines.append("Tips:")
        output_lines.extend(f"- {tip}" for tip in tips[:3])

    return {"result": "\n".join(output_lines)}


@app.post("/ats_check")
def ats_check(req: ResumeReq):
    check_paths_in_req(req)
    job_desc = req.job_description or ""
    resume_text = req.resume_text or ""

    required = _skills(job_desc)
    have = _skills(resume_text)
    matched = [s for s in required if s in have]
    missing = [s for s in required if s not in have]

    pct = round(100 * len(matched) / len(required)) if required else 0
    matched_str = ", ".join(matched) if matched else "None"
    missing_str = ", ".join(missing) if missing else "None"

    result = f"ATS Match: {pct}%\nMatched: {matched_str}\nMissing: {missing_str}"
    return {"result": result}


@app.post("/improve_resume")
def improve_resume(req: ResumeReq):
    check_paths_in_req(req)
    text = req.resume_text or ""
    improvements = []

    for phrase in WEAK_PHRASES:
        m = re.search(r'\b' + re.escape(phrase) + r'\b', text, re.IGNORECASE)
        if m:
            matched_text = m.group(0)
            improvements.append(
                f'- Replace "{matched_text.lower()}" with a strong action verb (e.g. Led/Built) and a measurable result.'
            )

    if not re.search(r"\d", text):
        improvements.append("- Add measurable metrics (numbers, percentages, or dollar amounts) to demonstrate impact.")

    have_skills = _skills(text)
    if len(have_skills) < 3:
        improvements.append("- Add a dedicated technical skills section listing your tools and frameworks.")

    if not improvements:
        result = "No major issues found."
    else:
        result = "\n".join(improvements)

    return {"result": result}


@app.post("/resume_to_pdf")
def resume_to_pdf(req: ResumeReq):
    check_paths_in_req(req)
    text = req.resume_data or req.resume_text or ""
    if not text:
        raise HTTPException(status_code=400, detail="Resume data cannot be empty")

    out_file = OUTPUTS_DIR / f"resume_{uuid4().hex[:8]}.pdf"
    c = canvas.Canvas(str(out_file), pagesize=letter)
    width, height = letter
    y = height - 50

    lines = text.strip().splitlines()
    if lines:
        title = lines[0].strip()
        c.setFont("Helvetica-Bold", 18)
        c.drawString(50, y, title)
        y -= 30

        c.setFont("Helvetica", 10)
        for line in lines[1:]:
            stripped = line.strip()
            if not stripped:
                y -= 14
                if y < 60:
                    c.showPage()
                    c.setFont("Helvetica", 10)
                    y = height - 50
                continue
            wrapped = textwrap.wrap(stripped, width=95)
            for w in wrapped:
                if y < 60:
                    c.showPage()
                    c.setFont("Helvetica", 10)
                    y = height - 50
                c.drawString(50, y, w)
                y -= 14
    c.save()

    return {"result": str(out_file.resolve())}


@app.post("/cover_letter")
def cover_letter(req: ResumeReq):
    check_paths_in_req(req)
    job_desc = req.job_description or ""
    resume_text = req.resume_text or ""

    m_comp = re.search(r"([A-Z][A-Za-z0-9&]+(?: [A-Z][A-Za-z0-9&]+)*) (?:is hiring|is looking)", job_desc)
    company = m_comp.group(1) if m_comp else "your company"

    m_role = re.search(r"hiring an? ([A-Z][\w ]+?)[.\n]", job_desc)
    role = m_role.group(1) if m_role else "this role"

    name = _name(resume_text)

    req_skills = _skills(job_desc)
    have_skills = _skills(resume_text)
    matched = [s for s in req_skills if s in have_skills]

    if matched:
        skills_text = f"My hands-on expertise in {', '.join(matched[:3])} directly matches your requirements."
    else:
        skills_text = "My background and technical experience make me well suited for this role."

    letter = (
        f"Dear Hiring Team at {company},\n\n"
        f"I am writing to express my strong interest in the {role} opportunity at {company}. "
        f"{skills_text} "
        f"I am eager to bring my problem-solving skills and technical background to your engineering team.\n\n"
        f"Thank you for your time and consideration. I look forward to speaking with you.\n\n"
        f"Sincerely,\n{name}"
    )
    return {"result": letter}


@app.post("/portfolio_generator")
def portfolio_generator(req: ResumeReq):
    check_paths_in_req(req)
    data = req.projects_data or ""
    articles = []

    for line in data.splitlines():
        line = line.strip()
        if not line:
            continue
        if ":" in line:
            parts = line.split(":", 1)
            title = parts[0].strip()
            desc = parts[1].strip()
        else:
            title = line
            desc = ""
        esc_title = html.escape(title)
        esc_desc = html.escape(desc)
        articles.append(
            f"    <article>\n      <h2>{esc_title}</h2>\n      <p>{esc_desc}</p>\n    </article>"
        )

    articles_html = "\n".join(articles)
    html_content = (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '  <meta charset="UTF-8">\n'
        "  <title>Portfolio</title>\n"
        "</head>\n"
        "<body>\n"
        "  <main>\n"
        f"{articles_html}\n"
        "  </main>\n"
        "</body>\n"
        "</html>\n"
    )

    out_file = OUTPUTS_DIR / f"portfolio_{uuid4().hex[:8]}.html"
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(html_content)

    return {"result": str(out_file.resolve())}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8099)
