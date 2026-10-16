"""Pulls supporting clinical proof out of EHR notes and maps it to payer policy criteria."""
import re

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

CATEGORIES = {
    "failed_treatment": r"\b(failed|failure|no (?:significant )?(?:improvement|relief|response)|inadequate (?:response|relief)|did not respond|unresponsive|discontinued|refractory|despite|tried|completed \d+|course of)\b",
    "lab_value": r"\b(hba1c|a1c|egfr|creatinine|glucose|hemoglobin|wbc|crp|esr|ldl|bnp|troponin|inr|ef|ejection fraction)\b.{0,25}\d|\b\d+(?:\.\d+)?\s?(?:mg/dl|mmol/l|%|g/dl|ng/ml|mg/l|mm/hr)",
    "imaging": r"\b(mri|x-?ray|radiograph|ct scan|ultrasound|echo(?:cardiogram)?|imaging|kellgren|stenosis|herniation|effusion)\b",
    "neuro_exam": r"\b(weakness|numbness|paresthesia|radiculopathy|reflex(?:es)?|straight leg|sensory|motor|strength \d/5|foot drop|gait)\b",
    "duration": r"\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten|twelve)[\s-]+(?:\(\d+\)\s*)?(days?|weeks?|months?|years?)\b",
    "physician_rationale": r"\b(medically necessary|recommend(?:ed|s)?|indicated|plan(?:ned)?|rationale|in my (?:clinical )?opinion|clinically appropriate|necessary)\b",
    "functional": r"\b(pain (?:score|rating)|vas|oswestry|womac|adl|activities of daily living|functional|limited|unable to|difficulty|walk(?:ing)?|stairs)\b",
}
LABELS = {
    "failed_treatment": "Prior/failed treatment", "lab_value": "Lab / measurement", "imaging": "Imaging / diagnostics",
    "neuro_exam": "Examination finding", "duration": "Duration of condition", "physician_rationale": "Physician rationale",
    "functional": "Functional impact",
}
REQ_RE = re.compile(r"\b(must|required|requires?|at least|failed?|failure|documented|documentation|confirmed|covered when|medically necessary when|criteria)\b", re.I)
NOT_CRIT = re.compile(r"criteria below|may be denied|are denied|are returned|is denied|may be resubmitted|:\s*$", re.I)
ICD_RE = re.compile(r"\b[A-TV-Z][0-9][0-9AB](?:\.[0-9A-TV-Z]{1,4})?\b")


def split_sentences(text: str) -> list[str]:
    text = re.sub(r"[ \t]+", " ", text)
    parts = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [p.strip(" -•*\t") for p in parts if len(p.strip()) > 18]


def extract_icd(text: str) -> list[str]:
    seen = []
    for m in ICD_RE.findall(text or ""):
        if re.search(r"\d", m) and m not in seen and "." in m:
            seen.append(m)
    return seen[:6]


def tag(sentence: str) -> list[str]:
    return [k for k, rx in CATEGORIES.items() if re.search(rx, sentence, re.I)]


def extract_criteria(policy_hits: list[dict], limit: int = 7) -> list[dict]:
    crit, seen = [], set()
    for h in policy_hits:
        for s in split_sentences(h["text"]):
            if REQ_RE.search(s) and len(s) < 420 and not NOT_CRIT.search(s):
                key = re.sub(r"\W+", " ", s.lower())[:60]
                if key not in seen:
                    seen.add(key)
                    crit.append({"text": s.lstrip("0123456789.)( "), "policy_ref": h["ref"]})
    return crit[:limit]


def analyse(ehr_text: str, policy_hits: list[dict], query_hint: str = "") -> dict:
    sentences = split_sentences(ehr_text or "")
    criteria = extract_criteria(policy_hits)
    if not sentences:
        return {"evidence": [], "criteria": [{**c, "status": "missing", "score": 0.0, "evidence_ref": None} for c in criteria],
                "coverage": 0.0, "icd": []}

    ref_text = [c["text"] for c in criteria] + [h["text"] for h in policy_hits] + [query_hint]
    vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), sublinear_tf=True).fit(ref_text + sentences)
    S = vec.transform(sentences)
    policy_sim = cosine_similarity(S, vec.transform([h["text"] for h in policy_hits] + [query_hint])).max(axis=1) if policy_hits else [0] * len(sentences)

    scored = []
    for i, s in enumerate(sentences):
        cats = tag(s)
        score = float(policy_sim[i]) + 0.12 * len(cats)
        if cats:
            scored.append({"text": s, "categories": cats, "labels": [LABELS[c] for c in cats], "score": round(score, 3)})
    scored.sort(key=lambda x: -x["score"])
    # keep diversity: at most 3 per category-lead
    evidence, used = [], {}
    for ev in scored:
        lead = ev["categories"][0]
        if used.get(lead, 0) >= 3:
            continue
        used[lead] = used.get(lead, 0) + 1
        ev["ref"] = f"E{len(evidence) + 1}"
        evidence.append(ev)
        if len(evidence) >= 9:
            break

    # criteria coverage
    crit_out, met = [], 0.0
    if criteria:
        C = vec.transform([c["text"] for c in criteria])
        sim = cosine_similarity(C, S)
        for ci, c in enumerate(criteria):
            j = int(sim[ci].argmax())
            sc = float(sim[ci][j])
            status = "met" if sc >= 0.16 else "partial" if sc >= 0.08 else "missing"
            met += 1.0 if status == "met" else 0.5 if status == "partial" else 0.0
            ev_ref = next((e["ref"] for e in evidence if e["text"] == sentences[j]), None)
            if status != "missing" and not ev_ref:
                ev_ref = f"E{len(evidence) + 1}"
                evidence.append({"text": sentences[j], "categories": tag(sentences[j]) or ["physician_rationale"], "labels": [LABELS[(tag(sentences[j]) or ['physician_rationale'])[0]]], "score": round(sc, 3), "ref": ev_ref})
            crit_out.append({**c, "status": status, "score": round(sc, 3), "evidence_ref": ev_ref if status != "missing" else None})
        coverage = met / len(criteria)
    else:
        coverage = min(1.0, len(evidence) / 6)
    return {"evidence": evidence, "criteria": crit_out, "coverage": round(coverage, 3), "icd": extract_icd(ehr_text)}
