"""
Pulsarr - Cloudflare Access JWT validation + LAN bypass.

Twee toegangspaden:

1. Via Cloudflare (mTLS + Access):
   De request komt binnen via cloudflared, dat CF-* headers toevoegt.
   We valideren de CF_Authorization JWT tegen Cloudflare's publieke sleutels.

2. Via het lokale netwerk (LAN):
   Geen CF-* headers aanwezig, en het bron-IP is privaat.
   De request wordt toegestaan zonder JWT.

Beveiligingsafweging:
Iedereen op je LAN kan Pulsarr zonder login gebruiken. Zorg dat je LAN
vertrouwd is (geen IoT-apparaten, gasten-wifi, enz.). Wil je dit niet,
gebruik dan een SSH-tunnel in plaats van LAN-toegang.
"""

import ipaddress
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


# Private IP-ranges die als "LAN" worden beschouwd.
PRIVATE_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


def _is_private_ip(host: str) -> bool:
    """Controleer of een IP-adres in een private range valt."""
    if not host:
        return False
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return any(ip in net for net in PRIVATE_NETWORKS)


def _has_cloudflare_headers(request: Request) -> bool:
    """Detecteer of de request via Cloudflare Tunnel is binnengekomen.

    cloudflared voegt standaard CF-Ray en CF-Connecting-IP toe aan elke
    doorgestuurde request. Als een van deze headers aanwezig is, weten we
    dat de request niet rechtstreeks vanaf het LAN komt, maar via Cloudflare.
    """
    cf_markers = (
        "cf-ray",
        "cf-connecting-ip",
        "cf-visitor",
        "cf-ipcountry",
    )
    return any(header in request.headers for header in cf_markers)


def _get_public_keys() -> list:
    """Haal Cloudflare's publieke RSA-sleutels op voor JWT-verificatie."""
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
    """Valideer de CF_Authorization JWT."""
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
    """FastAPI dependency: combineer LAN-bypass en Cloudflare JWT-check.

    Volgorde:
    1. Als CF_ACCESS_DISABLED=1: sta altijd toe (lokale dev).
    2. Als de request CF-* headers heeft: het komt via Cloudflare,
       dus JWT is verplicht.
    3. Als de request GEEN CF-* headers heeft en van een privaat IP komt:
       LAN-toegang, sta toe zonder JWT.
    4. Anders: JWT verplicht (fail-safe voor publieke IPs).
    """
    if CF_ACCESS_DISABLED:
        return True

    # Cloudflare-verkeer: JWT altijd verplicht.
    if _has_cloudflare_headers(request):
        return _verify_token(request)

    # LAN-verkeer: alleen als het bron-IP privaat is.
    client_host = request.client.host if request.client else ""
    if _is_private_ip(client_host):
        return True

    # Publiek IP zonder CF-headers: onbekend pad, eis JWT.
    return _verify_token(request)