import io
import json
from datetime import date, timedelta

import httpx
from pypdf import PdfReader

from backend import config
from backend import database as db
from backend.data import demo
from backend.services import appeal_gen, deadlines, edi835, files, predictor

from .conftest import Client


def _appeal(c, claim_id):
    r = c.post(f"/api/claims/{claim_id}/appeal")
    assert r.status_code == 201, r.text
    return r.json()["appeal_id"]


# ---------------- 835 parser ----------------
def test_835_main_sample_ignores_patient_responsibility():
    claims = edi835.parse_835(demo.SAMPLES["main"].read_text())
    assert [c["denial_code"] for c in claims] == ["50", "16", "197", "151"]
    assert all(c["group_code"] == "CO" for c in claims)
    assert all(c["claim_no"] != "MC1003" for c in claims)  # the PR-only (co-insurance) claim


def test_835_synthetic_sample_group_split():
    claims = edi835.parse_835(demo.SAMPLES["synthetic"].read_text())
    assert len(claims) == 3
    roe = next(c for c in claims if c["claim_no"] == "TESTCLAIM002")
    assert roe["denial_code"] == "197" and roe["denied_amount"] == 600.0  # the PR 200 is not counted as payer denial


def test_835_rejects_garbage(biller):
    r = biller.post("/api/claims/import-835", files={"file": ("x.edi", b"hello world this is not an edi file")})
    assert r.status_code == 400


def test_import_skips_duplicates(seeded):
    r = seeded.post("/api/claims/seed-demo?sample=main").json()
    assert r["imported"] == 0 and r["skipped_duplicates"] == 4


# ---------------- reference data ----------------
def test_deadline_rules_and_group_codes():
    assert deadlines.RULES and deadlines.BASELINE["deadline_days"] == 180
    d = deadlines.deadline("ANY PAYER", (date.today() - timedelta(days=20)).isoformat())
    assert d["days_left"] == 160 and d["verified"] is False  # CSV row is not marked verified yet
    assert deadlines.group_info("CO")["meaning"] and deadlines.group_info("pr")["name"]


def test_code_dataset_search(biller):
    r = biller.get("/api/codes/search", params={"q": "authorization"}).json()
    assert r["counts"]["carc"] >= 2 and r["counts"]["eob"] > 0
    assert biller.get("/api/codes/list", params={"q": "197"}).json()["codes"][0]["code"] == "197"
    assert biller.get("/api/codes/carc/ZZZ9").status_code == 404


# ---------------- RAG, evidence, letters ----------------
def test_rag_filters_by_payer(seeded):
    rows = {c["claim_no"]: c for c in seeded.get("/api/claims").json()["claims"]}
    a = seeded.post(f"/api/claims/{rows['MC1001']['id']}/analyze").json()["analysis"]
    assert a["policy_hits"] and all(h["payer"] in ("MEDISURE HEALTH", "ALL") for h in a["policy_hits"])
    b = seeded.post(f"/api/claims/{rows['BH2001']['id']}/analyze").json()["analysis"]
    assert all(h["payer"] in ("BLUEHORIZON INSURANCE", "ALL") for h in b["policy_hits"])


def test_evidence_matching_statuses(seeded):
    rao = next(c for c in seeded.get("/api/claims").json()["claims"] if c["claim_no"] == "MC1001")
    a = seeded.post(f"/api/claims/{rao['id']}/analyze").json()["analysis"]
    st = {c["status"] for c in a["criteria"]}
    assert "met" in st and st & {"partial", "missing"}
    assert any(c["status"] == "met" and c["evidence_ref"] for c in a["criteria"])


def test_no_policy_is_stated_honestly(biller):
    biller.post("/api/claims/seed-demo?sample=synthetic")
    doe = next(c for c in biller.get("/api/claims").json()["claims"] if c["claim_no"] == "TESTCLAIM001")
    an = biller.post(f"/api/claims/{doe['id']}/analyze").json()["analysis"]
    assert an["no_policy"] is True
    ap = biller.get(f"/api/appeals/{_appeal(biller, doe['id'])}").json()["appeal"]
    assert "No published coverage policy" in ap["letter"]


def test_contractual_denial_not_appealable(biller):
    c = biller.post("/api/claims", json={"claim_no": "K1", "patient_name": "A B", "payer": "X", "billed_amount": 10, "denial_code": "45", "denied_on": "2026-09-01"}).json()["claim"]
    assert biller.post(f"/api/claims/{c['id']}/appeal").status_code == 400


# ---------------- Claude integration (mocked) ----------------
def _fake_llm(monkeypatch, reply):
    sent = {}

    def fake(payload):
        sent["payload"] = payload
        return reply
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setattr(appeal_gen, "_call_claude", fake)
    return sent


GOOD = "Dear reviewer, {{NAME_1}} was denied an MRI. The payer policy requires conservative therapy [P1]. The chart documents six weeks of failed therapy [E1]. " * 3 + "\nREFERENCES [P1] [E1]"


def test_llm_receives_deidentified_text_and_reply_is_restored(seeded, monkeypatch):
    sent = _fake_llm(monkeypatch, GOOD)
    rao = next(c for c in seeded.get("/api/claims").json()["claims"] if c["claim_no"] == "MC1001")
    ap = seeded.get(f"/api/appeals/{_appeal(seeded, rao['id'])}").json()["appeal"]
    prompt = json.dumps(sent["payload"])
    assert "Anita" not in prompt and "Rao" not in prompt and "{{NAME_1}}" in prompt
    assert ap["engine"].startswith("claude:") and "Anita Rao" in ap["letter"]


def test_citation_guard_discards_invented_sources(seeded, monkeypatch):
    _fake_llm(monkeypatch, GOOD.replace("[P1]", "[P9]"))
    rao = next(c for c in seeded.get("/api/claims").json()["claims"] if c["claim_no"] == "MC1001")
    ap = seeded.get(f"/api/appeals/{_appeal(seeded, rao['id'])}").json()["appeal"]
    assert ap["engine"] == "template:fallback-citation" and "[P9]" not in ap["letter"]


def test_llm_retries_with_backoff_then_succeeds(seeded, monkeypatch):
    calls = {"n": 0}

    class R:
        status_code = 200
        request = None

        def raise_for_status(self): pass
        def json(self): return {"content": [{"type": "text", "text": GOOD}]}

    def flaky(*a, **k):
        calls["n"] += 1
        if calls["n"] < 3:
            raise httpx.ConnectError("boom")
        return R()
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setattr(appeal_gen.httpx, "post", flaky)
    monkeypatch.setattr(appeal_gen, "BACKOFF", (0, 0, 0))
    rao = next(c for c in seeded.get("/api/claims").json()["claims"] if c["claim_no"] == "MC1001")
    ap = seeded.get(f"/api/appeals/{_appeal(seeded, rao['id'])}").json()["appeal"]
    assert calls["n"] == 3 and ap["engine"].startswith("claude:")


def test_llm_total_failure_falls_back_to_template(seeded, monkeypatch):
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setattr(appeal_gen.httpx, "post", lambda *a, **k: (_ for _ in ()).throw(httpx.ConnectError("down")))
    monkeypatch.setattr(appeal_gen, "BACKOFF", ())
    rao = next(c for c in seeded.get("/api/claims").json()["claims"] if c["claim_no"] == "MC1001")
    ap = seeded.get(f"/api/appeals/{_appeal(seeded, rao['id'])}").json()["appeal"]
    assert ap["engine"] == "template:fallback-api" and "[P1]" in ap["letter"]


# ---------------- PDF, exports, regenerate ----------------
def test_pdf_has_pramaan_watermark_and_packet_id(seeded):
    rao = next(c for c in seeded.get("/api/claims").json()["claims"] if c["claim_no"] == "MC1001")
    aid = _appeal(seeded, rao["id"])
    r = seeded.get(f"/api/appeals/{aid}/pdf")
    assert r.status_code == 200 and r.content[:4] == b"%PDF"
    reader = PdfReader(io.BytesIO(r.content))
    for page in reader.pages:
        txt = page.extract_text()
        assert "PRAMAAN AI" in txt and "Packet PA-" in txt
    assert reader.metadata.author == "Pramaan AI"


def test_exports_csv_zip_and_formula_injection(seeded):
    seeded.post("/api/claims", json={"claim_no": "=1+1", "patient_name": "=cmd|' /C calc'!A0", "payer": "X", "billed_amount": 5, "denial_code": "50"})
    csv_text = seeded.get("/api/export/claims.csv").content.decode("utf-8-sig")
    assert "'=cmd" in csv_text and ",=cmd" not in csv_text
    for c in seeded.get("/api/claims?page_size=2").json()["claims"]:
        if c["status"] == "denied" and c["denial_code"] != "50" or c["claim_no"] == "MC1001":
            _appeal(seeded, c["id"])
    z = seeded.get("/api/export/packets.zip")
    import zipfile
    assert z.status_code == 200 and any(n.endswith(".pdf") for n in zipfile.ZipFile(io.BytesIO(z.content)).namelist())
    assert seeded.get("/api/export/outcomes.csv").status_code == 200


def test_autosave_regenerate_and_outcome_tracking(seeded):
    cl = seeded.get("/api/claims").json()["claims"][0]
    aid = _appeal(seeded, cl["id"])
    assert seeded.patch(f"/api/appeals/{aid}", json={"letter": "edited by a human " * 20}).json()["appeal"]["letter"].startswith("edited")
    assert "edited" not in seeded.post(f"/api/appeals/{aid}/regenerate").json()["appeal"]["letter"]
    p = seeded.patch(f"/api/appeals/{aid}", json={"status": "won"}).json()["appeal"]
    assert p["outcome"] == "won" and p["recovered_amount"] > 0
    tl = [e["event"] for e in seeded.get(f"/api/claims/{cl['id']}/timeline").json()["events"]]
    assert tl[0] == "imported" and "appeal_generated" in tl and "appeal_won" in tl


# ---------------- listing, bulk, dashboard, notifications ----------------
def test_claims_pagination_sort_filter(seeded):
    r = seeded.get("/api/claims?page_size=2&sort=amount&order=asc").json()
    assert r["total"] == 4 and r["pages"] == 2 and len(r["claims"]) == 2
    assert r["claims"][0]["denied_amount"] <= r["claims"][1]["denied_amount"]
    assert seeded.get("/api/claims?payer=MEDISURE HEALTH").json()["total"] == 2
    assert seeded.get("/api/claims?q=verma").json()["total"] == 1
    assert all("deadline" in c for c in r["claims"])


def test_bulk_analyze_and_bulk_appeal(seeded):
    ids = [c["id"] for c in seeded.get("/api/claims").json()["claims"]]
    res = seeded.post("/api/claims/bulk/analyze", json={"ids": ids + [999999]}).json()["results"]
    assert sum(1 for r in res if r["ok"]) == 4 and not res[-1]["ok"]
    res = seeded.post("/api/claims/bulk/appeal", json={"ids": ids}).json()["results"]
    assert all(r["ok"] for r in res)


def test_dashboard_filters_and_model_badge(seeded):
    d = seeded.get("/api/dashboard").json()
    assert d["totals"]["claims"] == 4 and len(d["monthly"]) == 6 and d["model"]["kind"] == "synthetic"
    assert seeded.get("/api/dashboard?payer=BLUEHORIZON INSURANCE").json()["totals"]["claims"] == 2
    assert seeded.get("/api/dashboard?date_from=2030-01-01").json()["totals"]["claims"] == 0


def test_notifications_deadline_and_status(biller):
    old = (date.today() - timedelta(days=170)).isoformat()
    c = biller.post("/api/claims", json={"claim_no": "OLD1", "patient_name": "Old Case", "payer": "MEDISURE HEALTH", "billed_amount": 100, "denial_code": "50", "denied_on": old}).json()["claim"]
    n = biller.get("/api/notifications").json()
    assert n["unread"] >= 1 and any("days left" in x["title"] for x in n["notifications"])
    assert len(biller.get("/api/notifications").json()["notifications"]) == len(n["notifications"])  # no duplicates on refresh
    aid = _appeal(biller, c["id"])
    biller.patch(f"/api/appeals/{aid}", json={"status": "submitted"})
    assert any(x["kind"] == "status" for x in biller.get("/api/notifications").json()["notifications"])
    assert biller.post("/api/notifications/read-all").status_code == 200


# ---------------- isolation ----------------
def test_claim_isolation_between_users(seeded, patient):
    cid = seeded.get("/api/claims").json()["claims"][0]["id"]
    assert patient.get(f"/api/claims/{cid}").status_code == 404
    assert patient.post(f"/api/claims/{cid}/appeal").status_code == 404
    assert patient.post("/api/claims/import-835", files={"file": ("a.edi", b"x")}).status_code == 403


def test_policy_libraries_are_per_organisation(uniq):
    a, b = Client(), Client()
    a.signup(f"a{uniq}@o1.in", "biller", org="Org One")
    b.signup(f"b{uniq}@o2.in", "biller", org="Org Two")
    text = "ACME INSURANCE private policy. Coverage requires documented failure of two treatments and a signed physician letter for every request."
    pid = a.post("/api/policies", json={"payer": "ACME", "title": "ACME private", "content": text}).json()["id"]
    assert any(p["id"] == pid for p in a.get("/api/policies").json()["policies"])
    assert not any(p["id"] == pid for p in b.get("/api/policies").json()["policies"])
    assert b.get(f"/api/policies/{pid}").status_code == 404 and b.delete(f"/api/policies/{pid}").status_code == 404
    shared = next(p for p in b.get("/api/policies").json()["policies"] if p["shared"])
    assert b.delete(f"/api/policies/{shared['id']}").status_code == 404  # shared library is read-only
    code = a.get("/api/auth/org").json()["org"]["invite_code"]
    c = Client()
    c.signup(f"c{uniq}@o1.in", "biller", invite=code)
    assert any(p["id"] == pid for p in c.get("/api/policies").json()["policies"])  # teammates share the org library


def test_patient_cannot_upload_policy(patient):
    assert patient.post("/api/policies", json={"payer": "X", "title": "t", "content": "y" * 40}).status_code == 403


# ---------------- uploads ----------------
def test_upload_validation(seeded, monkeypatch):
    cid = seeded.get("/api/claims").json()["claims"][0]["id"]
    assert seeded.post(f"/api/claims/{cid}/notes-file", files={"file": ("evil.exe", b"MZ....")}).status_code == 415
    monkeypatch.setattr(config, "MAX_UPLOAD_BYTES", 10)
    assert seeded.post(f"/api/claims/{cid}/notes-file", files={"file": ("a.txt", b"x" * 50)}).status_code == 413


def test_docx_notes_upload(seeded):
    import docx
    d = docx.Document()
    d.add_paragraph("Patient has knee pain for 12 weeks and failed physical therapy and NSAIDs. MRI is medically necessary.")
    buf = io.BytesIO()
    d.save(buf)
    cid = seeded.get("/api/claims").json()["claims"][0]["id"]
    r = seeded.post(f"/api/claims/{cid}/notes-file", files={"file": ("notes.docx", buf.getvalue())})
    assert r.status_code == 200 and "failed physical therapy" in r.json()["claim"]["ehr_notes"]


def test_scanned_pdf_gives_clear_message_when_ocr_missing(seeded, monkeypatch):
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.rect(50, 50, 100, 100, fill=1)  # an "image-only" page: no text layer
    c.save()
    monkeypatch.setattr(files, "ocr_available", lambda: False)
    cid = seeded.get("/api/claims").json()["claims"][0]["id"]
    r = seeded.post(f"/api/claims/{cid}/notes-file", files={"file": ("scan.pdf", buf.getvalue())})
    assert r.status_code == 400 and "OCR" in r.json()["detail"]


# ---------------- predictor ----------------
def test_predictor_synthetic_then_trained(tmp_path, monkeypatch):
    monkeypatch.setattr(predictor, "MODEL_PATH", tmp_path / "p.json")
    predictor.reset_model()
    assert predictor.predict(0.5, 0.5, 0.5, True, "2026-09-01", 1000)["model_kind"] == "synthetic"
    X, y = predictor._synthetic(300, seed=1)
    predictor.save_trained(X, y)
    p = predictor.predict(0.5, 0.9, 0.9, True, "2026-09-01", 1000)
    assert p["model_kind"] == "trained" and 0 < p["probability"] < 1
    predictor.reset_model()
    monkeypatch.setattr(predictor, "MODEL_PATH", tmp_path / "gone.json")
    predictor.reset_model()


# ---------------- external APIs (mocked) ----------------
def test_icd_lookup_caches(patient, monkeypatch):
    calls = {"n": 0}

    class R:
        def raise_for_status(self): pass
        def json(self): return [1, ["M54.16"], None, [["M54.16", "Radiculopathy, lumbar region"]]]

    def fake_get(*a, **k):
        calls["n"] += 1
        return R()
    from backend.routers import icd
    monkeypatch.setattr(icd.httpx, "get", fake_get)
    q = f"radicul{calls}"[:20].replace("{", "").replace("}", "").replace("'", "").replace(":", "").replace(" ", "")
    assert patient.get(f"/api/icd/search?q={q}").json()["cached"] is False
    assert patient.get(f"/api/icd/search?q={q}").json()["cached"] is True and calls["n"] == 1


def test_fhir_disabled_and_enabled(seeded, monkeypatch):
    cid = seeded.get("/api/claims").json()["claims"][0]["id"]
    assert seeded.post(f"/api/fhir/claims/{cid}/import", json={"patient_id": "123"}).status_code == 501
    from backend.routers import fhir
    monkeypatch.setattr(config, "FHIR_ENABLED", True)
    monkeypatch.setattr(fhir, "assert_public_http_url", lambda u: u)
    bundles = {"Condition": {"entry": [{"resource": {"code": {"text": "Lumbar radiculopathy"}, "onsetDateTime": "2026-06-01"}}]},
               "Observation": {"entry": [{"resource": {"code": {"text": "Pain score"}, "valueQuantity": {"value": 8, "unit": "/10"}}}]}, "Procedure": {}}
    monkeypatch.setattr(fhir, "_get", lambda path, params: bundles[path])
    assert seeded.post(f"/api/fhir/claims/{cid}/import", json={"patient_id": "123"}).json()["imported"] == 2
    assert seeded.post(f"/api/fhir/claims/{cid}/import", json={"patient_id": "../etc"}).status_code == 422


def test_contact_form_stores_and_emails(monkeypatch):
    sent = {}
    from backend.routers import misc
    monkeypatch.setattr(config, "CONTACT_TO", "team@example.org")
    monkeypatch.setattr(misc, "send_mail", lambda to, s, b: sent.update(to=to) or True)
    r = Client().post("/api/contact", json={"name": "Dr Test", "email": "dr@clinic.org", "kind": "partner", "message": "We would like to pilot this at our clinic."})
    assert r.status_code == 201 and r.json()["emailed"] is True and sent["to"] == "team@example.org"
    assert db.q1("SELECT COUNT(*) AS n FROM contact_messages WHERE email='dr@clinic.org'")["n"] == 1


# ---------------- public / dynamic content ----------------
def test_public_endpoints_are_dynamic(seeded):
    s = Client().get("/api/public/stats").json()
    assert s["codes"] == s["carc"] + s["rarc"] + s["eob"] and s["policies"] >= 5
    before = s["appeals"]
    _appeal(seeded, seeded.get("/api/claims").json()["claims"][0]["id"])
    after = Client().get("/api/public/stats").json()
    assert after["appeals"] == before + 1 and after["avg_win_probability"] is not None
    content = Client().get("/api/site/content").json()
    assert content["stats"] and content["faq"] and content["team"]
    assert "MEDISURE HEALTH" in Client().get("/api/payers").json()["payers"]
    assert Client().get("/api/procedures?q=knee").json()["procedures"]


def test_health_reports_integrations(monkeypatch):
    h = Client().get("/api/health").json()
    assert set(h["integrations"]) >= {"ai", "mail", "google", "fhir", "ocr"} and h["db"] == "sqlite" and h["policy_chunks"] > 0
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "x")
    assert Client().get("/api/health").json()["integrations"]["ai"] is True


def test_eligibility_check_is_labelled_with_model_kind():
    r = Client().post("/api/public/eligibility", json={"denial_code": "50", "amount": 1800, "days_since_denial": 20, "has_records": True}).json()
    assert r["verdict"] and r["model_kind"] in ("synthetic", "trained")


# ---------------- Free AI providers: Gemini / Ollama / OpenAI-compatible (mocked) ----------------
def _provider_env(monkeypatch, **vals):
    base = dict(LLM_PROVIDER="", ANTHROPIC_API_KEY="", GEMINI_API_KEY="", OPENAI_COMPAT_BASE_URL="", OPENAI_COMPAT_API_KEY="", OPENAI_COMPAT_MODEL="")
    base.update(vals)
    for k, v in base.items():
        monkeypatch.setattr(config, k, v)


def test_provider_selection_rules(monkeypatch):
    _provider_env(monkeypatch)
    assert config.llm_provider() == ""
    _provider_env(monkeypatch, GEMINI_API_KEY="g")
    assert config.llm_provider() == "gemini" and config.llm_label() == "gemini"
    _provider_env(monkeypatch, GEMINI_API_KEY="g", ANTHROPIC_API_KEY="a")
    assert config.llm_provider() == "anthropic" and config.llm_label() == "claude"        # auto prefers anthropic
    _provider_env(monkeypatch, GEMINI_API_KEY="g", ANTHROPIC_API_KEY="a", LLM_PROVIDER="gemini")
    assert config.llm_provider() == "gemini"                                             # explicit choice wins
    _provider_env(monkeypatch, LLM_PROVIDER="ollama")
    assert config.llm_provider() == "ollama"                                             # ollama needs no key but must be explicit
    _provider_env(monkeypatch, LLM_PROVIDER="gemini")
    assert config.llm_provider() == ""                                                   # forced provider without a key -> offline template


class _Resp:
    def __init__(self, body, code=200):
        self._b, self.status_code, self.request = body, code, None

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("x", request=httpx.Request("POST", "http://x"), response=httpx.Response(self.status_code))

    def json(self):
        return self._b


def _appeal_engine(seeded):
    rao = next(c for c in seeded.get("/api/claims").json()["claims"] if c["claim_no"] == "MC1001")
    return seeded.get(f"/api/appeals/{_appeal(seeded, rao['id'])}").json()["appeal"]


def test_gemini_uses_openai_compatible_endpoint(seeded, monkeypatch):
    _provider_env(monkeypatch, GEMINI_API_KEY="g-key")
    seen = {}

    def fake(url, **k):
        seen.update(url=url, **k)
        return _Resp({"choices": [{"message": {"content": GOOD}}]})
    monkeypatch.setattr(appeal_gen.httpx, "post", fake)
    ap = _appeal_engine(seeded)
    assert seen["url"].endswith("/v1beta/openai/chat/completions") and seen["headers"]["Authorization"] == "Bearer g-key"
    assert "Anita" not in json.dumps(seen["json"]) and seen["json"]["messages"][0]["role"] == "system"
    assert ap["engine"].startswith("gemini:") and "Anita Rao" in ap["letter"]


def test_ollama_uses_local_chat_endpoint_without_key(seeded, monkeypatch):
    _provider_env(monkeypatch, LLM_PROVIDER="ollama")
    monkeypatch.setattr(config, "OLLAMA_BASE_URL", "http://localhost:11434")
    seen = {}

    def fake(url, **k):
        seen.update(url=url, **k)
        return _Resp({"message": {"role": "assistant", "content": GOOD}})
    monkeypatch.setattr(appeal_gen.httpx, "post", fake)
    ap = _appeal_engine(seeded)
    assert seen["url"] == "http://localhost:11434/api/chat" and seen["json"]["stream"] is False
    assert "Anita" not in json.dumps(seen["json"]) and ap["engine"].startswith("ollama:")


def test_openai_compatible_provider(seeded, monkeypatch):
    _provider_env(monkeypatch, OPENAI_COMPAT_BASE_URL="https://api.example.test/v1", OPENAI_COMPAT_API_KEY="k", OPENAI_COMPAT_MODEL="m1")
    monkeypatch.setattr(appeal_gen.httpx, "post", lambda url, **k: _Resp({"choices": [{"message": {"content": GOOD}}]}) if url == "https://api.example.test/v1/chat/completions" else _Resp({}, 404))
    assert _appeal_engine(seeded)["engine"] == "openai_compatible:m1"


def test_small_local_model_with_bad_citations_falls_back(seeded, monkeypatch):
    _provider_env(monkeypatch, LLM_PROVIDER="ollama")
    monkeypatch.setattr(appeal_gen.httpx, "post", lambda url, **k: _Resp({"message": {"content": GOOD.replace("[P1]", "[P7]")}}))
    assert _appeal_engine(seeded)["engine"] == "template:fallback-citation"


def test_ollama_down_falls_back_without_retry_storm(seeded, monkeypatch):
    _provider_env(monkeypatch, LLM_PROVIDER="ollama")
    calls = {"n": 0}

    def down(*a, **k):
        calls["n"] += 1
        raise httpx.ConnectError("ollama not running")
    monkeypatch.setattr(appeal_gen.httpx, "post", down)
    assert _appeal_engine(seeded)["engine"] == "template:fallback-api" and calls["n"] == 1


def test_health_reports_provider(monkeypatch):
    _provider_env(monkeypatch, GEMINI_API_KEY="g")
    i = Client().get("/api/health").json()["integrations"]
    assert i["ai"] is True and i["ai_provider"] == "gemini" and i["ai_model"]
