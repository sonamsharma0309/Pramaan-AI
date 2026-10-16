"""Retrieval-Augmented Generation (retrieval half): index payer policy manuals and
fetch the clauses that matter for a given denial.

Uses TF-IDF (unigrams + bigrams, sublinear tf) with cosine similarity, plus an exact
procedure-code boost. Runs fully offline; no API key needed.
"""
import re

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .. import config

_CACHE: dict = {}


def norm_payer(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", (s or "").lower()).strip()


def payer_matches(policy_payer: str, claim_payer: str) -> bool:
    p, c = norm_payer(policy_payer), norm_payer(claim_payer)
    if p in ("all", "general", "any"):
        return True
    return bool(p and c and (p in c or c in p or p.split()[0] == c.split()[0]))


def chunk_text(text: str, size: int = 650) -> list[str]:
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks, buf = [], ""
    for p in paras:
        if len(buf) + len(p) + 2 <= size:
            buf = f"{buf}\n\n{p}".strip()
        else:
            if buf:
                chunks.append(buf)
            if len(p) > size * 1.6:  # very long paragraph: split on sentences
                sents, cur = re.split(r"(?<=[.;])\s+", p), ""
                for s in sents:
                    if len(cur) + len(s) > size and cur:
                        chunks.append(cur.strip())
                        cur = ""
                    cur += s + " "
                buf = cur.strip()
            else:
                buf = p
    if buf:
        chunks.append(buf)
    return chunks


def _build(policies: list[dict]):
    key = tuple((p["id"], len(p["content"])) for p in policies)
    if key in _CACHE:
        return _CACHE[key]
    chunks = []
    for p in policies:
        for i, ch in enumerate(chunk_text(p["content"])):
            chunks.append({"policy_id": p["id"], "title": p["title"], "payer": p["payer"], "chunk": i + 1, "text": ch})
    if not chunks:
        return None
    vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), sublinear_tf=True, min_df=1)
    X = vec.fit_transform([c["text"] for c in chunks])
    if len(_CACHE) > 20:
        _CACHE.clear()
    _CACHE[key] = (vec, X, chunks)
    return _CACHE[key]


_EMB: dict = {}


def _embedding_scores(query: str, texts: list[str]):
    """Optional semantic scores. Active only when EMBEDDINGS=true and sentence-transformers is installed."""
    if not config.EMBEDDINGS:
        return None
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        return None
    if "m" not in _EMB:
        _EMB["m"] = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    m = _EMB["m"]
    key = hash(tuple(texts))
    if _EMB.get("k") != key:
        _EMB["k"], _EMB["v"] = key, m.encode(texts, normalize_embeddings=True)
    return _EMB["v"] @ m.encode([query], normalize_embeddings=True)[0]


def embeddings_active() -> bool:
    if not config.EMBEDDINGS:
        return False
    try:
        import sentence_transformers  # noqa: F401
        return True
    except ImportError:
        return False


def retrieve(query: str, policies: list[dict], k: int = 4, boost_terms: list[str] | None = None) -> list[dict]:
    built = _build(policies)
    if not built or not query.strip():
        return []
    vec, X, chunks = built
    sims = cosine_similarity(vec.transform([query]), X)[0].copy()
    emb = _embedding_scores(query, [c["text"] for c in chunks])
    if emb is not None:  # hybrid: half lexical (TF-IDF), half semantic (sentence-transformers)
        sims = 0.5 * sims + 0.5 * np.clip(emb, 0, 1)
    for t in boost_terms or []:
        if t:
            for i, c in enumerate(chunks):
                if t.lower() in c["text"].lower():
                    sims[i] += 0.25
    order = np.argsort(-sims)[:k]
    hits = []
    for rank, i in enumerate(order, 1):
        if sims[i] <= 0.02:
            continue
        c = chunks[i]
        hits.append({"ref": f"P{rank}", "score": round(float(min(sims[i], 1.0)), 3), **c})
    return hits


def policy_match_score(hits: list[dict]) -> float:
    """0..1 confidence that the payer policy really addresses this service."""
    if not hits:
        return 0.0
    top = sorted((h["score"] for h in hits), reverse=True)[:2]
    return float(min(1.0, (sum(top) / len(top)) / 0.40))
