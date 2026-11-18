"""Pulsarr - CSRF helpers.

Double-submit cookie patroon:
- Token wordt in een cookie gezet (niet HttpOnly, JS moet lezen).
- Client stuurt dezelfde waarde mee via form-veld of header.
- Server vergelijkt cookie en meegestuurde waarde.

Secure-flag wordt per request bepaald op basis van het werkelijke
scheme, niet op basis van env-vars. Reden: op LAN HTTP werkt een
Secure-cookie niet (browser stuurt hem niet terug, JS kan hem niet
lezen). Alleen HTTPS (direct of via Cloudflare/proxy) krijgt Secure.
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
    existing = request.cookies.get(COOKIE_NAME)
    if existing:
        return existing, False
    return generate_token(), True


def extract_submitted_token(
    request: Request,
    body: bytes,
) -> str | None:
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


def should_set_secure(request: Request) -> bool:
    """Bepaal Secure-flag op basis van werkelijk scheme.

    - Direct HTTPS                  → True
    - X-Forwarded-Proto: https       → True (proxy/cloudflared)
    - Cloudflare (cf-ray aanwezig)   → True (CF termineert TLS)
    - Anders (LAN HTTP, dev)         → False
    """
    if request.url.scheme == "https":
        return True

    forwarded = (
        request.headers.get("x-forwarded-proto", "")
        .lower()
        .split(",")[0]
        .strip()
    )
    if forwarded == "https":
        return True

    if request.headers.get("cf-ray"):
        return True

    return False
