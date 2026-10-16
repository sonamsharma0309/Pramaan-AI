"""Denial-code knowledge base used to interpret denials.

Official CARC / RARC / EOB descriptions come from the bundled dataset data/carc_rarc.json
(CARC-RARC consolidated list, posted 02/12/2026). The curated CARC table below only adds
appeal strategy and a prior win rate for the most common codes.

`base_win` is a prior probability that a well-documented first-level appeal succeeds.
These are illustrative priors for the demo; replace with your own historical outcomes.
"""

import json
import re
from pathlib import Path

_DS = json.loads((Path(__file__).resolve().parent.parent / "data" / "carc_rarc.json").read_text(encoding="utf-8"))
DATASET_SOURCE = _DS["source"]
CARC_DESC: dict = _DS["carc"]
RARC_DESC: dict = _DS["rarc"]
EOB: dict = _DS["eob"]

CARC = {
    "1": ("Deductible amount", "patient_responsibility", 0.02, "Patient responsibility. Not normally appealable."),
    "2": ("Coinsurance amount", "patient_responsibility", 0.02, "Patient responsibility. Not normally appealable."),
    "3": ("Co-payment amount", "patient_responsibility", 0.02, "Patient responsibility. Not normally appealable."),
    "4": ("Procedure code inconsistent with modifier or missing modifier", "coding", 0.72, "Correct the modifier and submit a corrected claim with a short appeal."),
    "11": ("Diagnosis inconsistent with procedure", "coding", 0.66, "Verify ICD-10 to CPT linkage; justify the diagnosis pointer with clinical notes."),
    "15": ("Authorization number missing or invalid", "authorization", 0.55, "Attach authorization number or request retro-authorization."),
    "16": ("Claim lacks information or has billing errors", "administrative", 0.74, "Identify the missing field (see remark code), supply it, and resubmit."),
    "18": ("Exact duplicate claim or service", "administrative", 0.35, "Confirm the original claim status; appeal only if the first was never paid."),
    "22": ("Care may be covered by another payer (coordination of benefits)", "administrative", 0.50, "Provide COB information or primary payer EOB."),
    "27": ("Expenses incurred after coverage terminated", "eligibility", 0.20, "Verify eligibility dates; appeal only with proof of active coverage."),
    "29": ("Time limit for filing has expired", "timely_filing", 0.28, "Provide proof of timely filing (clearinghouse acceptance report)."),
    "50": ("Not deemed a medical necessity by the payer", "medical_necessity", 0.62, "Cite payer medical-necessity criteria and map each criterion to chart evidence."),
    "55": ("Procedure/treatment deemed experimental or investigational", "medical_necessity", 0.38, "Provide peer-reviewed evidence and clinical rationale."),
    "96": ("Non-covered charge(s)", "coverage", 0.30, "Check plan benefits; appeal with exception criteria if any."),
    "97": ("Benefit included in payment for another service", "coding", 0.45, "Justify separate billing with distinct-service documentation (modifier 59/XS)."),
    "119": ("Benefit maximum reached for this period", "coverage", 0.22, "Verify accumulators; appeal only with medical exception."),
    "151": ("Payment adjusted: information does not support the number/frequency of services", "medical_necessity", 0.58, "Document functional progress and the clinical need for the frequency/units billed."),
    "167": ("Diagnosis not covered", "coverage", 0.40, "Show covered diagnosis or exception criteria."),
    "197": ("Precertification/authorization/notification absent", "authorization", 0.52, "Attach auth number or request retro-authorization with urgency/clinical justification."),
    "204": ("Service/equipment not covered under the patient's current benefit plan", "coverage", 0.32, "Check plan documents; appeal with exception criteria if any."),
    "252": ("Additional documentation needed to process the claim", "administrative", 0.78, "Send the requested documentation."),
}

CATEGORY_LABEL = {
    "medical_necessity": "Medical necessity",
    "authorization": "Authorization",
    "coding": "Coding / modifier",
    "administrative": "Administrative / missing info",
    "timely_filing": "Timely filing",
    "eligibility": "Eligibility",
    "coverage": "Coverage / benefits",
    "patient_responsibility": "Patient responsibility",
    "contractual": "Contractual adjustment",
    "unknown": "Unclassified",
}

CATEGORY_KEYWORDS = {
    "medical_necessity": "medical necessity criteria clinical conservative therapy failed documented indicated",
    "authorization": "prior authorization precertification notification urgent retrospective review",
    "coding": "coding modifier diagnosis procedure linkage ICD-10 CPT distinct service",
    "administrative": "documentation required information submitted complete claim form",
    "timely_filing": "timely filing deadline submission days clearinghouse",
    "eligibility": "eligibility enrollment coverage effective dates",
    "coverage": "covered benefit exclusion exception plan",
    "unknown": "medical necessity documentation criteria",
    "contractual": "fee schedule contract rate allowed amount",
}

REMARK = {
    "N115": "Decision based on a Local Coverage Determination (LCD).",
    "N386": "Decision based on a National Coverage Determination (NCD) or LCD.",
    "M62": "Missing/incomplete/invalid treatment authorization code.",
    "N54": "Claim information is inconsistent with pre-certified/authorized services.",
    "N479": "Missing Explanation of Benefits (Coordination of Benefits or Medicare Secondary Payer).",
    "MA130": "Claim contains incomplete or invalid information.",
    "M76": "Missing/incomplete/invalid diagnosis or condition.",
}

CPT = {
    "72148": "MRI lumbar spine without contrast",
    "72141": "MRI cervical spine without contrast",
    "27447": "Total knee arthroplasty",
    "97110": "Therapeutic exercise (each 15 min)",
    "97140": "Manual therapy techniques",
    "93306": "Transthoracic echocardiogram, complete with Doppler",
    "70553": "MRI brain with and without contrast",
    "99213": "Office visit, established patient (low-moderate)",
    "99214": "Office visit, established patient (moderate)",
    "45378": "Diagnostic colonoscopy",
    "73721": "MRI lower extremity joint without contrast",
    "99215": "Office visit, established patient (high)",
    "20610": "Arthrocentesis, major joint",
}



_RULES = [
    ("patient_responsibility", r"deductible|coinsurance|co-?payment|patient responsib"),
    ("contractual", r"fee schedule|contracted|contractual|allowable"),
    ("authorization", r"authoriz|precert|referral|pre-treatment|notification"),
    ("timely_filing", r"time limit|timely|filing"),
    ("medical_necessity", r"medical necessity|experimental|investigational|frequency|many/|not support|exceeds? .*(frequency|number)"),
    ("eligibility", r"eligib|terminated|enroll|not covered by this payer|coverage not in effect"),
    ("coding", r"modifier|diagnosis|procedure code|inconsistent|included in the allowance|bundled|unbundl"),
    ("administrative", r"lacks information|missing|invalid|incomplete|submission|billing error|duplicate|additional documentation"),
    ("coverage", r"non-?covered|not covered|benefit|maximum|exclu|not eligible"),
]
_PRIOR = {"medical_necessity": 0.55, "authorization": 0.50, "coding": 0.60, "administrative": 0.70, "timely_filing": 0.25,
          "eligibility": 0.20, "coverage": 0.30, "patient_responsibility": 0.02, "contractual": 0.05, "unknown": 0.40}
_STRATEGY = {
    "medical_necessity": "Cite the payer's medical-necessity criteria and map each criterion to a dated chart entry.",
    "authorization": "Attach the authorization number or request retro-authorization with clinical justification.",
    "coding": "Verify CPT/ICD-10 linkage and modifiers; send a corrected claim with a short supporting statement.",
    "administrative": "Find the missing or invalid field (see the remark code), correct it and resubmit with supporting documents.",
    "timely_filing": "Provide proof of timely filing (clearinghouse acceptance report).",
    "eligibility": "Verify coverage dates; appeal only with proof of active coverage.",
    "coverage": "Check plan benefits and exclusions; appeal only if an exception applies.",
    "patient_responsibility": "Patient responsibility. Not normally appealable.",
    "contractual": "Contractual adjustment under the fee schedule. Not normally appealable unless the contract rate was misapplied.",
    "unknown": "Review the EOB text and remark codes manually.",
}


def _norm(code: str) -> str:
    c = (code or "").strip().upper()
    c = re.sub(r"^(CARC|CO|PR|OA|PI|CR)[-\s:]*", "", c)
    return c.strip()


def _classify(desc: str) -> str:
    d = (desc or "").lower()
    for cat, rx in _RULES:
        if re.search(rx, d):
            return cat
    return "unknown"


def remark_desc(code: str) -> str:
    c = (code or "").strip().upper()
    return RARC_DESC.get(c) or REMARK.get(c, "")


def info(code: str) -> dict:
    code = _norm(code)
    official = CARC_DESC.get(code, "")
    if code in CARC:  # curated entry: category, prior and strategy tuned for appeals
        desc, cat, base, tip = CARC[code]
    else:
        cat = _classify(official)
        desc, base, tip = official or "Unrecognised denial code", _PRIOR[cat], _STRATEGY[cat]
    return {
        "code": code,
        "description": desc,
        "official_description": official or desc,
        "category": cat,
        "category_label": CATEGORY_LABEL[cat],
        "base_win": base,
        "strategy": tip,
        "appealable": cat not in ("patient_responsibility", "contractual"),
        "in_dataset": code in CARC_DESC,
    }


def search(q: str, limit: int = 40) -> dict:
    ql = (q or "").strip().lower()
    out = {"carc": [], "rarc": [], "eob": []}
    if not ql:
        return out
    for k, v in CARC_DESC.items():
        if ql == k.lower() or ql in v.lower():
            i = info(k)
            out["carc"].append({"code": k, "description": v, "category": i["category_label"], "strategy": i["strategy"]})
    for k, v in RARC_DESC.items():
        if ql == k.lower() or ql in v.lower():
            out["rarc"].append({"code": k, "description": v})
    for k, v in EOB.items():
        if ql == k.lower() or ql in v["desc"].lower():
            out["eob"].append({**v, "carc_desc": CARC_DESC.get(v["carc"], ""), "rarc_desc": RARC_DESC.get(v["rarc"], "")})
    return {k: v[:limit] for k, v in out.items()} | {"counts": {k: len(v) for k, v in out.items()}}
