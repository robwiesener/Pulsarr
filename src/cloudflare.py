"""
Pulsarr - Cloudflare Access JWT validation.

Cloudflare Access zit vóór de app en valideert mTLS-certificaten.
Na succesvolle validatie zet Cloudflare een CF_Authorization cookie
met een JWT. Deze module verifieert die JWT zodat de app zeker weet
dat de request via Cloudflare Access is gekomen.
"""

import json
import os

import jwt
import requests
from fastapi import HTTPException, Request


TEAM_DOMAIN = os.getenv(
    "CF_ACCESS_TEAM_DOMAIN",
    "https://<jouw-team>.cloudflareaccess.com",
)

POLICY_AUD = os.getenv("CF_ACCESS_AUD", "<jouw-aud-tag>")

CERTS_URL = f"{TEAM_DOMAIN}/cdn-cgi/access/certs"

CF_ACCESS_DISABLED = os.getenv("CF_ACCESS_DISABLED", "0") == "1"


def _get_public_keys() -> list:
    response = requests.get(CERTS_URL, timeout=10)
    response.raise_for_status()
    jwk_set = response.json()

    public_keys = []
    for key_dict in jwk_set["keys"]:
        public_key = jwt.algorithms.RSAAlgorithm.from_jwk(
            json.dumps(key_dict)
        )
        public_keys.append(public_key)
    return public_keys


def _verify_token(request: Request) -> bool:
    token = request.cookies.get("CF_Authorization")

    if not token:
        token = request.headers.get("Cf-Access-Jwt-Assertion")

    if not token:
        raise HTTPException(
            status_code=400,
            detail="Missing Cloudflare Access token",
        )

    keys = _get_public_keys()

    for key in keys:
        try:
            jwt.decode(
                token,
                key=key,
                audience=POLICY_AUD,
                algorithms=["RS256"],
            )
            return True
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=401,
                detail="Token expired",
            )
        except jwt.InvalidTokenError:
            continue

    raise HTTPException(
        status_code=401,
        detail="Invalid Cloudflare Access token",
    )


async def validate_cloudflare(request: Request):
    if CF_ACCESS_DISABLED:
        return True
    return _verify_token(request)