"""Pulsarr - CSRF helpers.

Double-submit cookie patroon:
- Token wordt in een cookie gezet (niet HttpOnly, JS moet lezen).
- Client stuurt dezelfde waarde mee via form-veld of header.
- Server vergelijkt cookie en meegestuurde waarde.

Token is niet geheim (het is een nonce), maar moet per sessie uniek
zijn. Cookie-instellingen: SameSite=Lax, Secure conditioneel.
"""

import secrets
from urllib.parse import parse_qs

from starlette.requests import Request


COOKIE_NAME = "csrf_token"
HEADER_NAME = "x-csrf-token"
FORM_FIELD = "csrf_token"
TOKEN_BYTES = 32


SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def generate_token() -> str:
    return secrets.token_urlsafe(TOKEN_BYTES)


def get_or_create_cookie_token(request: Request) -> tuple[str, bool]:
    """Return (token, was_created).

    Als de cookie al bestaat, wordt die hergebruikt. Anders wordt een
    nieuwe token gegenereerd.
    """
    existing = request.cookies.get(COOKIE_NAME)
    if existing:
        return existing, False
    return generate_token(), True


def extract_submitted_token(
    request: Request,
    body: bytes,
) -> str | None:
    """Haal de meegestuurde token op uit header of form-body."""
    header_value = request.headers.get(HEADER_NAME)
    if header_value:
        return header_value

    content_type = request.headers.get("content-type", "").lower()

    if (
        "application/x-www-form-urlencoded" not in content_type
        and "multipart/form-data" not in content_type
    ):
        return None

    try:
        text = body.decode("utf-8", errors="ignore")
    except Exception:
        return None

    parsed = parse_qs(text, keep_blank_values=False)
    values = parsed.get(FORM_FIELD)
    if not values:
        return None
    return values[0]


def tokens_match(a: str | None, b: str | None) -> bool:
    if not a or not b:
        return False
    return secrets.compare_digest(a, b)


def cookie_secure() -> bool:
    """Secure-flag alleen als auth aan staat (dus niet in dev)."""
    import os
    disabled = os.getenv("CF_ACCESS_DISABLED", "0") == "1"
    return not disabled
