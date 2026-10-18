import pytest

from backend.services import deid, net


def test_deidentify_removes_identifiers_and_restores():
    text = "Anita Rao DOB: 01/02/1980 phone (555) 123-4567 email a@b.com SSN 123-45-6789 MRN: AB12345 needs MRI."
    clean, m = deid.deidentify(text, ["Anita Rao"])
    for secret in ("Anita", "Rao", "123-45-6789", "a@b.com", "555", "AB12345", "01/02/1980"):
        assert secret not in clean
    assert deid.reinsert(clean, m) == text


def test_ssrf_guard_blocks_private_targets():
    for bad in ("http://127.0.0.1/x", "http://169.254.169.254/latest/meta-data", "file:///etc/passwd", "ftp://example.com", "http://10.0.0.5"):
        with pytest.raises(net.UnsafeURL):
            net.assert_public_http_url(bad)


def test_security_headers_and_request_id(biller):
    r = biller.get("/api/health")
    assert "default-src 'self'" in r.headers["content-security-policy"]
    assert r.headers["x-frame-options"] == "DENY" and len(r.headers["x-request-id"]) == 12
    assert "no-store" in r.headers["cache-control"]
