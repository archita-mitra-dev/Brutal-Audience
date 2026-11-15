"""Passwords, login tokens, request authentication and login throttling.

Choices worth knowing about
---------------------------
* Passwords are hashed with scrypt from the standard library (memory-hard, salted per
  user). The plain password is never stored or logged.
* Login tokens are signed JWTs (HS256) sent as `Authorization: Bearer <token>`.
* Every request re-reads the user from the database, so deleting an account
  invalidates its tokens immediately.
* Failed logins are throttled per (email, IP) in memory. That protects a single server
  process; behind several workers you would move it to a shared store.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import secrets
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from . import db
from .config import get_settings

log = logging.getLogger("brutal_audience.auth")

# --- password hashing --------------------------------------------------------------
_N, _R, _P = 2**14, 8, 1


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P, dklen=32)
    return "scrypt${}${}${}${}${}".format(
        _N, _R, _P, base64.b64encode(salt).decode(), base64.b64encode(dk).decode()
    )


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt_b64, dk_b64 = stored.split("$")
        if scheme != "scrypt":
            return False
        salt, expected = base64.b64decode(salt_b64), base64.b64decode(dk_b64)
        dk = hashlib.scrypt(password.encode(), salt=salt, n=int(n), r=int(r), p=int(p), dklen=len(expected))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(dk, expected)


# Used when the email is unknown, so "no such user" and "wrong password" take similar time.
DUMMY_HASH = hash_password("not-a-real-password")

# --- tokens --------------------------------------------------------------------------
_generated_secret: str | None = None


def _secret() -> str:
    global _generated_secret
    configured = get_settings().jwt_secret
    if configured:
        return configured
    if _generated_secret is None:
        _generated_secret = secrets.token_urlsafe(48)
        log.warning("JWT_SECRET is not set: using a random key for this process. "
                    "Logins will not survive a restart. Set JWT_SECRET in production.")
    return _generated_secret


def create_token(user_id: str) -> str:
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=get_settings().jwt_expire_minutes)
    return jwt.encode({"sub": user_id, "iat": now, "exp": exp}, _secret(), algorithm="HS256")


def decode_token(token: str) -> str | None:
    """Returns the user id, or None for anything invalid or expired."""
    try:
        payload = jwt.decode(token, _secret(), algorithms=["HS256"], options={"require": ["exp", "sub"]})
    except jwt.PyJWTError:
        return None
    sub = payload.get("sub")
    return sub if isinstance(sub, str) else None


# --- request authentication ------------------------------------------------------------
_bearer = HTTPBearer(auto_error=False)


def current_user(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> dict:
    unauthorised = HTTPException(401, "Please log in to continue.", headers={"WWW-Authenticate": "Bearer"})
    if creds is None:
        raise unauthorised
    user_id = decode_token(creds.credentials)
    user = db.get_user(user_id) if user_id else None
    if user is None:
        raise unauthorised
    return user


# --- login throttling ----------------------------------------------------------------------
class LoginThrottle:
    def __init__(self) -> None:
        self._fails: dict[str, deque[float]] = defaultdict(deque)

    def _prune(self, key: str, now: float) -> deque[float]:
        q = self._fails[key]
        window = get_settings().login_window_s
        while q and now - q[0] > window:
            q.popleft()
        return q

    def check(self, key: str) -> None:
        now = time.monotonic()
        q = self._prune(key, now)
        if len(q) >= get_settings().login_max_failures:
            wait = int(get_settings().login_window_s - (now - q[0])) + 1
            raise HTTPException(429, f"Too many failed attempts. Try again in {max(wait, 1)} seconds.",
                                headers={"Retry-After": str(max(wait, 1))})

    def fail(self, key: str) -> None:
        self._fails[key].append(time.monotonic())

    def clear(self, key: str) -> None:
        self._fails.pop(key, None)

    def reset(self) -> None:
        self._fails.clear()


throttle = LoginThrottle()
