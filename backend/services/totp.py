"""RFC 6238 TOTP (HMAC-SHA1, 30 s, 6 digits) with a QR code for authenticator apps."""
import base64
import hashlib
import hmac
import io
import secrets
import struct
import time
from urllib.parse import quote


def new_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def _code(secret: str, counter: int) -> str:
    key = base64.b32decode(secret + "=" * (-len(secret) % 8))
    h = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    o = h[-1] & 0x0F
    return f"{(struct.unpack('>I', h[o:o + 4])[0] & 0x7FFFFFFF) % 10**6:06d}"


def totp_now(secret: str, at: float | None = None) -> str:
    return _code(secret, int((at or time.time()) // 30))


def verify(secret: str, code: str, window: int = 1) -> bool:
    code = (code or "").strip().replace(" ", "")
    if not (secret and code.isdigit() and len(code) == 6):
        return False
    c = int(time.time() // 30)
    return any(hmac.compare_digest(_code(secret, c + d), code) for d in range(-window, window + 1))


def provisioning_uri(secret: str, email: str, issuer: str = "Pramaan AI") -> str:
    return f"otpauth://totp/{quote(issuer)}:{quote(email)}?secret={secret}&issuer={quote(issuer)}&digits=6&period=30"


def qr_svg_data_uri(uri: str) -> str:
    import qrcode
    import qrcode.image.svg
    img = qrcode.make(uri, image_factory=qrcode.image.svg.SvgPathImage, box_size=8)
    buf = io.BytesIO()
    img.save(buf)
    return "data:image/svg+xml;base64," + base64.b64encode(buf.getvalue()).decode()
