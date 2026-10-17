"""Create (or promote) an admin account. Admins can never be created through the public sign-up.

Usage:
  python scripts/create_admin.py --email you@example.org --name "Your Name"      # prompts for a password
  ADMIN_PASSWORD=... python scripts/create_admin.py --email you@example.org --name "Your Name"
"""
import argparse
import getpass
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend import database as db  # noqa: E402
from backend import security as sec


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--email", required=True)
    ap.add_argument("--name", default="Administrator")
    args = ap.parse_args()
    pw = os.getenv("ADMIN_PASSWORD") or getpass.getpass("Admin password: ")
    errs = sec.validate_password(pw, args.email)
    if errs:
        print("Password needs: " + ", ".join(errs), file=sys.stderr)
        return 1
    db.init_db()
    email = args.email.lower()
    existing = db.q1("SELECT id FROM users WHERE email=?", (email,))
    if existing:
        db.ex("UPDATE users SET role='admin', password_hash=?, email_verified=1, name=? WHERE id=?", (sec.hash_password(pw), args.name, existing["id"]))
        print(f"Updated {email} -> admin")
    else:
        db.ex("INSERT INTO users(name,email,password_hash,role,email_verified) VALUES(?,?,?,?,1)", (args.name, email, sec.hash_password(pw), "admin"))
        print(f"Created admin {email}")
    print("Sign in at /#/login/admin")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
