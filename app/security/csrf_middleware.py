"""Pulsarr - CSRF middleware.

Genereert bij elke request (indien nodig) een CSRF-cookie en
verifieert POST/PUT/PATCH/DELETE tegen cookie + meegestuurde token.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.security.csrf import (
    COOKIE_NAME,
    SAFE_METHODS,
    cookie_secure,
    extract_submitted_token,
    get_or_create_cookie_token,
    tokens_match,
)


class CSRFMiddleware(BaseHTTPMiddleware):

    async def dispatch(self, request: Request, call_next):
        token, created = get_or_create_cookie_token(request)
        request.state.csrf_token = token

        if request.method in SAFE_METHODS:
            response = await call_next(request)
            if created:
                self._set_cookie(response, token)
            return response

        body = await request.body()
        submitted = extract_submitted_token(request, body)

        if not tokens_match(token, submitted):
            response = JSONResponse(
                status_code=403,
                content={
                    "detail": (
                        "CSRF token missing or invalid. "
                        "Reload the page and try again."
                    )
                },
            )
            if created:
                self._set_cookie(response, token)
            return response

        # Body is al gelezen; hergebruik voor downstream.
        async def receive():
            return {
                "type": "http.request",
                "body": body,
                "more_body": False,
            }

        request._receive = receive

        response = await call_next(request)
        if created:
            self._set_cookie(response, token)
        return response

    def _set_cookie(self, response, token: str) -> None:
        response.set_cookie(
            key=COOKIE_NAME,
            value=token,
            max_age=60 * 60 * 24 * 7,
            httponly=False,
            samesite="lax",
            secure=cookie_secure(),
            path="/",
        )
