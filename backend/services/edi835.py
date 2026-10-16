"""Minimal but real ANSI X12 835 (Electronic Remittance Advice) parser.

Extracts denied / under-paid claims with their CARC adjustment codes, remark codes,
patient, payer, procedure and dates. Handles multiple ST..SE transactions per file.
"""
import re
from datetime import datetime

from .denial_codes import CPT, info, remark_desc


def _date(s: str) -> str:
    try:
        return datetime.strptime(s[:8], "%Y%m%d").strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return ""


def _f(s: str) -> float:
    try:
        return float(s)
    except (ValueError, TypeError):
        return 0.0


def _split(text: str):
    text = text.replace("\ufeff", "").strip()
    elem, seg, sub = "*", "~", ":"
    if text.startswith("ISA") and len(text) > 105:
        elem, sub = text[3], text[104]
        cand = text[105]
        if not cand.isalnum() and cand not in " ":
            seg = cand
    parts = [s.strip() for s in text.split(seg)]
    if len([p for p in parts if p]) <= 1 and "\n" in text:
        parts = [s.strip() for s in text.splitlines()]
    return [p for p in parts if p], elem, sub


def _el(e: list[str], i: int) -> str:
    """Element i of a segment, or empty string when absent."""
    return e[i] if len(e) > i else ""


def parse_835(text: str) -> list[dict]:
    if "CLP" not in text:
        raise ValueError("This does not look like an 835 file (no CLP segments found).")
    segments, E, S = _split(text)
    payer, payment_date = "", ""
    claims, cur = [], None

    def flush():
        nonlocal cur
        if cur:
            claims.append(cur)
        cur = None

    for seg in segments:
        e = seg.split(E)
        tag = e[0]
        if tag == "ST":
            flush()
            payer, payment_date = "", ""
        elif tag == "BPR":
            payment_date = _date(_el(e, 16))
        elif tag == "N1" and _el(e, 1) == "PR":
            payer = _el(e, 2)
        elif tag == "CLP":
            flush()
            cur = {
                "claim_no": _el(e, 1), "status_code": _el(e, 2), "billed_amount": _f(_el(e, 3)), "paid_amount": _f(_el(e, 4)),
                "patient_resp": _f(_el(e, 5)), "payer": payer, "denied_on": payment_date,
                "patient_name": "", "procedure_code": "", "procedure_desc": "",
                "service_date": "", "remark_code": "", "adjustments": [],
            }
        elif cur is None:
            continue
        elif tag == "NM1" and _el(e, 1) == "QC":
            cur["patient_name"] = f"{_el(e, 4).title()} {_el(e, 3).title()}".strip()
        elif tag == "CAS":
            grp = _el(e, 1)
            for i in range(2, len(e) - 1, 3):
                if _el(e, i):
                    cur["adjustments"].append({"group": grp, "code": _el(e, i), "amount": _f(_el(e, i + 1))})
        elif tag == "SVC":
            comp = _el(e, 1).split(S)
            code = comp[1] if len(comp) > 1 else comp[0]
            cur["procedure_code"] = cur["procedure_code"] or code
            cur["procedure_desc"] = cur["procedure_desc"] or CPT.get(code, f"Procedure {code}")
        elif tag == "DTM" and _el(e, 1) in ("232", "472", "150"):
            cur["service_date"] = cur["service_date"] or _date(_el(e, 2))
        elif tag == "LQ" and _el(e, 1) == "HE":
            cur["remark_code"] = cur["remark_code"] or _el(e, 2)
    flush()

    out = []
    for c in claims:
        adj = [a for a in c["adjustments"] if a["group"] != "PR"]  # PR = patient responsibility, not a payer denial
        is_denied = c["status_code"] == "4" or c["paid_amount"] < c["billed_amount"]
        if not adj or not is_denied:
            continue
        main = max(adj, key=lambda a: a["amount"])
        d = info(main["code"])
        denied_amt = sum(a["amount"] for a in adj) or (c["billed_amount"] - c["paid_amount"])
        reason = d["description"]
        if c["remark_code"]:
            reason += f" (remark {c['remark_code']}: {remark_desc(c['remark_code']) or 'see payer EOB'})"
        out.append({
            "claim_no": c["claim_no"], "patient_name": c["patient_name"] or "Unknown patient", "payer": c["payer"] or "Unknown payer",
            "procedure_code": c["procedure_code"], "procedure_desc": c["procedure_desc"], "diagnosis": "",
            "billed_amount": c["billed_amount"], "denied_amount": round(denied_amt, 2),
            "denial_code": main["code"], "denial_reason": reason, "remark_code": c["remark_code"],
            "service_date": c["service_date"], "denied_on": c["denied_on"], "group_code": main["group"], "adjustments": c["adjustments"],
        })
    return out


def norm_name(s: str) -> str:
    return re.sub(r"[^a-z ]", "", (s or "").lower()).strip()
