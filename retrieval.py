from pathlib import Path
import re

POLICY_PATH = Path(__file__).parent / "data" / "student_policy.txt"

def _chunks():
    raw = POLICY_PATH.read_text(encoding="utf-8")
    sections = [s.strip() for s in re.split(r"\n(?=## )", raw) if s.strip()]
    result = []
    for i, section in enumerate(sections):
        heading = section.splitlines()[0].replace("#", "").strip()
        result.append({"source": POLICY_PATH.name, "chunk_id": f"policy-{i+1}", "heading": heading, "text": section})
    return result

def retrieve_policy(query, top_k=2):
    terms = set(re.findall(r"[a-zA-Z]{3,}", query.lower()))
    scored = []
    for chunk in _chunks():
        text_terms = set(re.findall(r"[a-zA-Z]{3,}", (chunk["heading"] + " " + chunk["text"]).lower()))
        score = len(terms & text_terms)
        if score:
            scored.append((score, chunk))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [chunk for score, chunk in scored[:top_k]]
