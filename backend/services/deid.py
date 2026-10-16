"""Best-effort PHI de-identification before text leaves the server (e.g. to an LLM API).

Replaces known patient names plus SSN, phone, e-mail, DOB and MRN/member-id patterns with numbered
placeholders and can restore them in the model's reply. This is a safety net, not a certified
HIPAA Safe-Harbor tool: free-text notes can still contain identifiers the patterns do not catch.
"""
import re

PATTERNS: list[tuple[str, re.Pattern]] = [
    ("SSN", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("EMAIL", re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")),
    ("DOB", re.compile(r"\b(?:DOB|D\.O\.B\.?|date of birth|born)\s*[:\-]?\s*\d{1,4}[/\-.]\d{1,2}[/\-.]\d{1,4}\b", re.I)),
    ("MRN", re.compile(r"\b(?:MRN|medical record (?:number|no\.?)|member id|patient id)\s*[:#]?\s*[A-Z0-9-]{4,}\b", re.I)),
    ("PHONE", re.compile(r"(?<![\w.])(?:\+?\d{1,3}[ .-]?)?(?:\(\d{3}\)|\d{3})[ .-]?\d{3}[ .-]?\d{4}(?![\w])")),
]


def deidentify(text: str, names: list[str] | None = None) -> tuple[str, dict[str, str]]:
    """Return (clean_text, mapping placeholder -> original)."""
    mapping: dict[str, str] = {}
    counters: dict[str, int] = {}

    def put(kind: str, original: str) -> str:
        for ph, orig in mapping.items():
            if orig == original and ph.startswith("{{" + kind):
                return ph
        counters[kind] = counters.get(kind, 0) + 1
        ph = f"{{{{{kind}_{counters[kind]}}}}}"
        mapping[ph] = original
        return ph

    out = text or ""
    tokens: list[str] = []
    for n in names or []:
        n = (n or "").strip()
        if len(n) >= 3:
            tokens.append(n)
            tokens += [t for t in re.split(r"[\s,]+", n) if len(t) >= 3]
    for tok in sorted(set(tokens), key=len, reverse=True):
        out = re.sub(r"\b" + re.escape(tok) + r"\b", lambda m: put("NAME", m.group(0)), out, flags=re.I)
    for kind, rx in PATTERNS:
        out = rx.sub(lambda m, k=kind: put(k, m.group(0)), out)
    return out, mapping


def reinsert(text: str, mapping: dict[str, str]) -> str:
    for ph, orig in mapping.items():
        text = text.replace(ph, orig)
    return text
