"""Demo sign-in: password hashing, signed tokens and access rules.

This is prototype-grade access control so the owner view only ever shows the
signed-in owner's business. It is not production authentication (no MFA,
rate limiting, refresh tokens or KYC).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import get_session
from .models import User

SECRET = os.environ.get("CREDIPATH_SECRET", "credipath-demo-secret-change-me").encode()
TOKEN_TTL_SECONDS = 12 * 3600

# Public sample accounts shown on the sign-in page. All fictional.
DEMO_ACCOUNTS = [
    {"email": "officer@demobank.in", "password": "Banker@123", "role": "banker", "display_name": "Priya Menon", "organisation": "Demo Co-operative Bank · MSME loans", "business_id": None},
    {"email": "raj@rajsbakery.in", "password": "Raj@123", "role": "merchant", "display_name": "Raj Kulkarni", "organisation": "Raj's Bakery", "business_id": "rajs-bakery"},
    {"email": "meena@meenastore.in", "password": "Meena@123", "role": "merchant", "display_name": "Meena Patil", "organisation": "Meena General Store", "business_id": "meena-general-store"},
    {"email": "anil@sharmamobile.in", "password": "Anil@123", "role": "merchant", "display_name": "Anil Sharma", "organisation": "Sharma Mobile & Electronics", "business_id": "sharma-mobile-electronics"},
    {"email": "lata@greenleaf.in", "password": "Lata@123", "role": "merchant", "display_name": "Lata Nair", "organisation": "Green Leaf Tiffin Services", "business_id": "green-leaf-tiffin"},
]


def hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(8)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000).hex()
    return f"pbkdf2${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, salt, _ = stored.split("$")
    except ValueError:
        return False
    return hmac.compare_digest(hash_password(password, salt), stored)


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def make_token(user: User) -> str:
    payload = _b64(json.dumps({"email": user.email, "role": user.role, "exp": int(time.time()) + TOKEN_TTL_SECONDS}).encode())
    sig = _b64(hmac.new(SECRET, payload.encode(), hashlib.sha256).digest())
    return f"{payload}.{sig}"


def read_token(token: str) -> dict | None:
    try:
        payload, sig = token.split(".")
        expected = _b64(hmac.new(SECRET, payload.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, expected):
            return None
        data = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        return data if data.get("exp", 0) > time.time() else None
    except Exception:
        return None


def user_dict(u: User) -> dict:
    return {"email": u.email, "role": u.role, "display_name": u.display_name, "organisation": u.organisation, "business_id": u.business_id}


def current_user(authorization: str | None = Header(default=None), db: Session = Depends(get_session)) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Please sign in.")
    data = read_token(authorization.split(" ", 1)[1])
    if data is None:
        raise HTTPException(401, "Your session has expired. Please sign in again.")
    user = db.scalars(select(User).where(User.email == data["email"])).first()
    if user is None:
        raise HTTPException(401, "This account no longer exists (the demo may have been reset). Please sign in again.")
    return user


def require_banker(user: User = Depends(current_user)) -> User:
    if user.role != "banker":
        raise HTTPException(403, "Only lender accounts can do this.")
    return user


def check_business_access(user: User, business_id: str) -> None:
    """Bankers may open any applicant; a merchant only their own business."""
    if user.role == "merchant" and user.business_id != business_id:
        raise HTTPException(403, "You can only view your own business.")


def seed_demo_users(db: Session) -> list[str]:
    from .models import Business

    created = []
    for acc in DEMO_ACCOUNTS:
        if db.scalars(select(User).where(User.email == acc["email"])).first():
            continue
        if acc["business_id"] and db.get(Business, acc["business_id"]) is None:
            continue
        db.add(
            User(
                email=acc["email"],
                password_hash=hash_password(acc["password"]),
                role=acc["role"],
                display_name=acc["display_name"],
                organisation=acc["organisation"],
                business_id=acc["business_id"],
                is_demo=True,
            )
        )
        created.append(acc["email"])
    return created
