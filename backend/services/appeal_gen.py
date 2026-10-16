"""Appeal letter generation and the watermarked PDF packet.

Engine 1 (optional): an LLM - Claude, Gemini (free tier), Ollama (local, free) or any OpenAI-compatible API - grounded only on retrieved policy clauses and chart evidence.
  - PHI is de-identified before the call and restored in the reply (DEIDENTIFY_BEFORE_LLM).
  - Citation guard: if the model cites a [P#]/[E#] that was not supplied, its letter is discarded.
  - Transient API errors are retried with exponential backoff.
Engine 2 (default, offline): deterministic template. If no payer policy was found, the letter says so honestly.
"""
import hashlib
import io
import json
import re
import time
from datetime import date
from xml.sax.saxutils import escape

import httpx

from .. import config
from . import deid

BACKOFF = (1.0, 2.0, 4.0)  # seconds between retries; tests patch this to ()
CITE_RE = re.compile(r"\[([PE]\d+)\]")
NO_POLICY_NOTE = ("NOTE ON POLICY: No published coverage policy from this payer for this service was available in our library when this "
                  "letter was prepared, so it does not quote payer-specific criteria. It relies on the clinical record excerpts below.")


class CitationError(ValueError):
    """The LLM cited a source that was not in the retrieved context."""


def _money(x) -> str:
    return f"${float(x or 0):,.2f}"


def _short(s: str, n: int = 260) -> str:
    s = " ".join(s.split())
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def allowed_refs(a: dict) -> set[str]:
    return {h["ref"] for h in a["policy_hits"]} | {e["ref"] for e in a["evidence"]}


def template_letter(claim: dict, a: dict, user: dict) -> str:
    today = date.today().strftime("%B %d, %Y")
    patient = user.get("role") == "patient"
    org = user.get("org") or ("" if patient else "Provider practice")
    d = a["denial"]
    L = [today, "", f"{claim['payer']}", "Attn: Appeals / Grievance Department", "",
         f"RE: Request for reconsideration of denied claim {claim['claim_no']}", f"Patient: {claim['patient_name']}",
         f"Service: {claim.get('procedure_desc') or 'Service'} (CPT {claim.get('procedure_code') or 'n/a'})",
         f"Date of service: {claim.get('service_date') or 'see claim'}    Amount in dispute: {_money(claim.get('denied_amount') or claim.get('billed_amount'))}",
         f"Denial reason: CARC {d['code']} - {d['official_description'] or d['description']}", "", "To the Appeals Reviewer:", ""]
    if patient:
        L.append(f"I am writing to request reconsideration of the above denial. My treating clinician recommended this service, and the records below "
                 f"{'show that it meets' if a['policy_hits'] else 'support its medical necessity under'} {claim['payer']}'s coverage criteria.")
    else:
        L.append(f"On behalf of {org}, we respectfully request reconsideration of the above denial. The service was clinically appropriate, and the "
                 f"documentation below {'shows that it meets' if a['policy_hits'] else 'supports its medical necessity under'} {claim['payer']}'s coverage criteria.")
    L.append("")
    if a.get("no_policy"):
        L += [NO_POLICY_NOTE, ""]
    if a["evidence"]:
        L.append("CLINICAL SUMMARY")
        L += [f"  - {_short(e['text'])} [{e['ref']}]" for e in a["evidence"][:6]]
        L.append("")
    met = [c for c in a["criteria"] if c["status"] in ("met", "partial") and c.get("evidence_ref")]
    if met:
        L.append("HOW THE PAYER'S POLICY CRITERIA ARE MET")
        for c in met:
            L.append(f"  - Policy requirement: {_short(c['text'], 220)} [{c['policy_ref']}]")
            ev = next((e for e in a["evidence"] if e["ref"] == c["evidence_ref"]), None)
            if ev:
                L.append(f"    Supporting record: {_short(ev['text'], 200)} [{ev['ref']}]")
        L.append("")
    elif a["policy_hits"]:
        L += ["APPLICABLE POLICY", f"  - {_short(a['policy_hits'][0]['text'], 320)} [P1]", ""]
    L += ["REQUEST", f"Based on the clinical documentation{'' if a.get('no_policy') else ' and ' + claim['payer'] + chr(39) + 's own medical policy'}, we ask that the denial be "
          "overturned and the claim reprocessed for payment. If additional records are needed, or if a peer-to-peer review with the treating physician would help, "
          "please contact " + ("me." if patient else "our office."), "",
          "Enclosures: clinical notes excerpts, payer policy excerpts, copy of remittance advice (835/EOB).", "", "Sincerely,", "", user.get("name", "")]
    L += ([org] if org else []) + ["", "REFERENCES"]
    L += [f"  [{h['ref']}] {h['payer']} - {h['title']} (section {h['chunk']})" for h in a["policy_hits"]]
    L += [f"  [{e['ref']}] Patient record excerpt ({', '.join(e['labels'])})" for e in a["evidence"]]
    return "\n".join(L)


def _facts(claim: dict, a: dict, user: dict) -> dict:
    return {
        "claim": {k: claim.get(k) for k in ("claim_no", "patient_name", "payer", "procedure_code", "procedure_desc", "service_date", "denied_amount", "diagnosis")},
        "denial": {"code": a["denial"]["code"], "description": a["denial"]["official_description"], "category": a["denial"]["category_label"]},
        "policy_clauses": [{"ref": h["ref"], "title": h["title"], "text": h["text"]} for h in a["policy_hits"]],
        "chart_evidence": [{"ref": e["ref"], "text": e["text"]} for e in a["evidence"]],
        "criteria_status": [{"criterion": c["text"], "status": c["status"], "evidence_ref": c["evidence_ref"]} for c in a["criteria"]],
        "no_policy_found": bool(a.get("no_policy")), "signer": {"name": user.get("name"), "organization": user.get("org"), "role": user.get("role")},
    }


SYSTEM = ("You are a medical billing appeals specialist. Write a formal, concise appeal letter (max ~550 words, plain text, no markdown). "
          "Use ONLY the facts supplied. Cite policy clauses as [P#] and chart evidence as [E#] after each claim, using only references that exist in the input. "
          "Never invent lab values, dates, diagnoses or policy text. If a criterion is 'missing', do not assert it is met. "
          "If no_policy_found is true, say honestly that no payer policy was available and rely on chart evidence only. "
          "If signer.role is 'patient', write in the first person as the patient. Keep any {{PLACEHOLDER}} tokens exactly as written. "
          "End with a REFERENCES list mapping every [P#]/[E#] used.")


RETRYABLE = (429, 500, 502, 503, 504, 529)


def _request(provider: str, payload: dict) -> str:
    """One HTTP call to the chosen provider. `payload` is the Anthropic-style dict built in claude_letter()."""
    system, messages, max_tokens = payload["system"], payload["messages"], payload.get("max_tokens", 1800)
    if provider == "anthropic":
        r = httpx.post("https://api.anthropic.com/v1/messages",
                       headers={"x-api-key": config.ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                       json=payload, timeout=60)
        parse = lambda j: "".join(b.get("text", "") for b in j.get("content", []) if b.get("type") == "text")  # noqa: E731
    elif provider == "ollama":
        body = {"model": config.OLLAMA_MODEL, "stream": False, "messages": [{"role": "system", "content": system}, *messages],
                "options": {"num_predict": max_tokens, "temperature": 0.2}}
        r = httpx.post(f"{config.OLLAMA_BASE_URL}/api/chat", json=body, timeout=300)  # local CPU models can be slow
        parse = lambda j: (j.get("message") or {}).get("content", "")  # noqa: E731
    else:  # gemini or any OpenAI-compatible endpoint
        base, key, model = ((config.GEMINI_BASE_URL, config.GEMINI_API_KEY, config.GEMINI_MODEL) if provider == "gemini"
                            else (config.OPENAI_COMPAT_BASE_URL, config.OPENAI_COMPAT_API_KEY, config.OPENAI_COMPAT_MODEL))
        # "thinking" models spend part of the budget on reasoning, so leave generous head-room
        body = {"model": model, "temperature": 0.2, "max_tokens": max(max_tokens, 4096),
                "messages": [{"role": "system", "content": system}, *messages]}
        r = httpx.post(f"{base}/chat/completions", headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"}, json=body, timeout=90)
        parse = lambda j: ((j.get("choices") or [{}])[0].get("message") or {}).get("content") or ""  # noqa: E731
    if r.status_code in RETRYABLE:
        raise httpx.HTTPStatusError("retryable", request=r.request, response=r)
    r.raise_for_status()
    return parse(r.json()).strip()


def _call_claude(payload: dict) -> str:
    """Call the active LLM provider with retry + exponential backoff. (Name kept for backwards compatibility.)"""
    provider = config.llm_provider()
    backoff = () if provider == "ollama" else BACKOFF  # a slow local model should not be retried for minutes
    last: Exception | None = None
    for attempt in range(len(backoff) + 1):
        try:
            return _request(provider, payload)
        except (httpx.TransportError, httpx.HTTPStatusError) as e:
            last = e
            if isinstance(e, httpx.HTTPStatusError) and e.response.status_code not in RETRYABLE:
                break
            if attempt < len(backoff):
                time.sleep(backoff[attempt])
    raise last or RuntimeError("LLM request failed")


def claude_letter(claim: dict, a: dict, user: dict) -> str:
    facts_json = json.dumps(_facts(claim, a, user), indent=2)
    mapping: dict[str, str] = {}
    if config.DEIDENTIFY_BEFORE_LLM:
        names = [claim.get("patient_name", "")] + ([user.get("name", "")] if user.get("role") == "patient" else [])
        facts_json, mapping = deid.deidentify(facts_json, names)
    text = _call_claude({"model": config.llm_model(), "max_tokens": 1800, "system": SYSTEM,
                         "messages": [{"role": "user", "content": "Draft the appeal letter from these facts:\n" + facts_json}]})
    text = deid.reinsert(text, mapping)
    if len(text) < 200:
        raise ValueError("Empty model response")
    cited = set(CITE_RE.findall(text))
    bad = cited - allowed_refs(a)
    if bad:
        raise CitationError(f"Model cited unknown sources: {sorted(bad)}")
    if allowed_refs(a) and not cited:
        raise CitationError("Model letter contains no citations")
    return text


def generate(claim: dict, a: dict, user: dict, force_llm: bool = False) -> tuple[str, str]:
    """Return (letter, engine). Engine is '<provider>:<model>' (e.g. 'claude:...', 'gemini:...', 'ollama:...'), 'template' or 'template:fallback-<reason>'."""
    if config.llm_provider():
        engine = f"{config.llm_label()}:{config.llm_model()}"
        try:
            return claude_letter(claim, a, user), engine
        except CitationError:
            return template_letter(claim, a, user), "template:fallback-citation"
        except Exception:
            return template_letter(claim, a, user), "template:fallback-api"
    return template_letter(claim, a, user), "template"


# ------------------------------------------------------------------ PDF packet
def packet_id(appeal: dict) -> str:
    h = hashlib.sha256(f"{appeal['id']}|{appeal.get('letter', '')}".encode()).hexdigest()[:10].upper()
    return f"PA-{int(appeal['id']):06d}-{h}"


def _watermark(pid: str):
    def draw(canv, doc):
        from reportlab.lib import colors
        w, h = doc.pagesize
        canv.saveState()
        canv.setFillColor(colors.HexColor("#3B3BD6"))
        canv.setFillAlpha(0.07)
        canv.setFont("Helvetica-Bold", 46)
        canv.translate(w / 2, h / 2)
        canv.rotate(35)
        for dy in range(-700, 701, 190):  # tiled so the mark cannot be cropped out
            for dx in range(-700, 701, 420):
                canv.drawCentredString(dx, dy, "PRAMAAN AI")
        canv.restoreState()
        canv.saveState()
        canv.setFont("Helvetica", 7.5)
        canv.setFillColor(colors.HexColor("#5A6B7C"))
        canv.drawString(20 * 2.835, 9 * 2.835, f"Generated by Pramaan AI  |  Packet {pid}  |  Draft for human review, not legal advice")
        canv.drawRightString(w - 20 * 2.835, 9 * 2.835, f"Page {canv.getPageNumber()}")
        canv.restoreState()
    return draw


def build_pdf(claim: dict, appeal: dict, a: dict) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    pid = packet_id(appeal)
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=18 * mm, bottomMargin=20 * mm,
                            title=f"Appeal packet - claim {claim['claim_no']}", author="Pramaan AI", subject=f"Packet {pid}", creator="Pramaan AI")
    ss = getSampleStyleSheet()
    body = ParagraphStyle("b", parent=ss["BodyText"], fontName="Helvetica", fontSize=10, leading=14)
    h = ParagraphStyle("h", parent=ss["Heading2"], fontName="Helvetica-Bold", fontSize=12, spaceBefore=10, spaceAfter=6, textColor=colors.HexColor("#10202E"))
    small = ParagraphStyle("s", parent=body, fontSize=8.5, leading=11, textColor=colors.HexColor("#4A5A68"))
    flow = [Paragraph(escape(p).replace("  ", "&nbsp;&nbsp;") or "&nbsp;", body) for p in (appeal["letter"] or "").split("\n")]
    flow.append(PageBreak())
    flow.append(Paragraph("Appendix A - Evidence and criteria audit trail", h))
    kind = (a.get("prediction") or {}).get("model_kind", "synthetic")
    flow.append(Paragraph(f"Estimated appeal strength: {round((appeal.get('win_probability') or 0) * 100)}% "
                          f"({'estimate from a model trained on synthetic data' if kind == 'synthetic' else 'model trained on recorded outcomes'}; not a guarantee). Packet ID {pid}.", small))
    rows = [["Policy criterion", "Status", "Policy", "Evidence"]]
    rows += [[Paragraph(escape(c["text"][:200]), small), c["status"].upper(), c["policy_ref"], c.get("evidence_ref") or "-"] for c in a.get("criteria", [])]
    if len(rows) > 1:
        t = Table(rows, colWidths=[95 * mm, 20 * mm, 20 * mm, 25 * mm], repeatRows=1)
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#10202E")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                               ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#B8C2CC")), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        flow.append(t)
    flow.append(Paragraph("Appendix B - Payer policy excerpts", h))
    if not a.get("policy_hits"):
        flow.append(Paragraph("No payer policy for this service was available in the library when this packet was generated.", small))
    for p in a.get("policy_hits", []):
        flow.append(Paragraph(f"<b>[{p['ref']}] {escape(p['title'])}</b> - {escape(p['payer'])}", body))
        flow.append(Paragraph(escape(p["text"]).replace("\n", "<br/>"), small))
        flow.append(Spacer(1, 4))
    flow.append(Paragraph("Appendix C - Clinical record excerpts", h))
    for e in a.get("evidence", []):
        flow.append(Paragraph(f"<b>[{e['ref']}]</b> ({escape(', '.join(e['labels']))}) {escape(e['text'])}", small))
        flow.append(Spacer(1, 3))
    mark = _watermark(pid)
    doc.build(flow, onFirstPage=mark, onLaterPages=mark)
    return buf.getvalue()
