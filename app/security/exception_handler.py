"""Pulsarr - Generieke exception handler.

Vangt onverwachte exceptions af en voorkomt dat stacktraces of
exception-details naar de client lekken. Voor HTML-requests wordt
een nette error-pagina gerenderd; voor API-requests een generieke
JSON-response.

De fout wordt naar stderr gelogd (via print + traceback). NIET naar
de activity log: de database kan zelf de bron van de fout zijn.
"""

import traceback

from fastapi import Request
from fastapi.responses import JSONResponse

from app.templates import templates


async def generic_exception_handler(
    request: Request,
    exc: Exception,
):
    print(
        "UNHANDLED EXCEPTION: "
        f"{request.method} {request.url.path}"
    )
    traceback.print_exc()

    accept = request.headers.get("accept", "")

    if "text/html" in accept:
        try:
            return templates.TemplateResponse(
                request=request,
                name="error.html",
                context={},
                status_code=500,
            )
        except Exception:
            # Als de template zelf faalt, val terug op platte tekst.
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal server error"},
            )

    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )
