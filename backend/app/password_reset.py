"""
Forgotten-password codes for bookers, sent over WhatsApp.

A booker asks for a reset with their email; a 6-digit code goes to the phone
number saved on their account (email can't be used — Render's free tier blocks
it). The code is stored only as an HMAC (never in plain text), works once,
expires after 15 minutes and is locked after 5 wrong guesses. Asking again is
limited, and the answer to "forgot password" is identical whether or not the
email has an account, so it can't be used to find out who is registered.
"""
import hashlib
import hmac
import secrets
from datetime import timedelta

from app.config import settings

CODE_TTL = timedelta(minutes=15)
MAX_ATTEMPTS = 5
RESEND_COOLDOWN = timedelta(seconds=60)
MAX_CODES_PER_HOUR = 3

GENERIC_REPLY = "If that email has an account, we've sent a code to the WhatsApp number saved on it."


def new_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_code(email: str, code: str) -> str:
    key = settings.jwt_secret.encode()
    return hmac.new(key, f"{email.lower()}:{code}".encode(), hashlib.sha256).hexdigest()


def code_matches(email: str, code: str, stored_hash: str) -> bool:
    return hmac.compare_digest(hash_code(email, code), stored_hash)
