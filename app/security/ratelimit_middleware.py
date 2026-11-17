"""Pulsarr - Rate limiting middleware."""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.security.ratelimit import RateLimiter


GET_LIMIT = 100
GET_WINDOW = 60.0

POST_LIMIT = 20
POST_WINDOW = 60.0

SEARCH_LIMIT = 5
SEARCH_WINDOW = 60.0

SEARCH_PATH = "/wishlist/search"

EXEMPT_PREFIXES = ("/static/",)


class RateLimitMiddleware(BaseHTTPMiddleware):

    def __init__(self, app):
        super().__init__(app)
        self._limiter = RateLimiter()

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        if any(path.startswith(p) for p in EXEMPT_PREFIXES):
            return await call_next(request)

        ip = self._client_ip(request)

        if request.method == "POST" and path == SEARCH_PATH:
            limit, window = SEARCH_LIMIT, SEARCH_WINDOW
            bucket = f"search:{ip}"
        elif request.method in ("POST", "PUT", "PATCH", "DELETE"):
            limit, window = POST_LIMIT, POST_WINDOW
            bucket = f"write:{ip}"
        else:
            limit, window = GET_LIMIT, GET_WINDOW
            bucket = f"read:{ip}"

        allowed, remaining, retry_after = self._limiter.check(
            bucket, limit, window
        )

        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": (
                        "Rate limit exceeded. "
                        f"Retry after {retry_after} seconds."
                    )
                },
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response

    @staticmethod
    def _client_ip(request: Request) -> str:
        # Cloudflare Tunnel: CF-Connecting-IP is door Cloudflare gezet
        cf = request.headers.get("cf-connecting-ip")
        if cf:
            return cf.strip()

        # Cloudflare voegt ook X-Forwarded-For toe; eerste is client
        xfwd = request.headers.get("x-forwarded-for")
        if xfwd:
            return xfwd.split(",")[0].strip()

        if request.client:
            return request.client.host

        return "unknown"
