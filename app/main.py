from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends
from fastapi.staticfiles import StaticFiles

import app.models

from app.screens.wishlist_routes import router as wishlist_router
from app.screens.configuration_routes import router as settings_router
from app.screens.result_management_routes import router as result_management_router
from app.screens.library_routes import router as library_router
from app.screens.activity_log_routes import router as activity_log_router

from app.cloudflare import validate_cloudflare
from app.security.csrf_middleware import CSRFMiddleware
from app.security.ratelimit_middleware import RateLimitMiddleware
from app.security.headers import SecurityHeadersMiddleware
from app.security.exception_handler import generic_exception_handler

from app.db.database import create_db_and_tables

from app.services.background_service import background_service


@asynccontextmanager
async def lifespan(app: FastAPI):

    # Multi-worker guard: Pulsarr MOET met workers=1 draaien.
    # Achtergrondtaken draaien in-process en SQLite heeft geen
    # cross-process locking. Een file lock voorkomt per ongeluk
    # meerdere workers.
    import fcntl

    lock_file = open("/tmp/pulsarr.lock", "w")

    try:
        fcntl.flock(
            lock_file,
            fcntl.LOCK_EX | fcntl.LOCK_NB,
        )
    except BlockingIOError:
        raise RuntimeError(
            "Another Pulsarr worker is already running. "
            "Pulsarr must run with workers=1."
        )

    create_db_and_tables()

    await background_service.start()

    yield

    await background_service.stop()

    lock_file.close()


app = FastAPI(
    title="Pulsarr",
    lifespan=lifespan,
)

app.add_exception_handler(Exception, generic_exception_handler)

app.add_middleware(CSRFMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(SecurityHeadersMiddleware)


app.mount(
    "/static",
    StaticFiles(directory="app/static"),
    name="static",
)


# Alle routers achter Cloudflare Access-validatie
protected = [Depends(validate_cloudflare)]

app.include_router(
    wishlist_router,
    dependencies=protected,
)
app.include_router(
    settings_router,
    dependencies=protected,
)
app.include_router(
    result_management_router,
    dependencies=protected,
)
app.include_router(
    library_router,
    dependencies=protected,
)
app.include_router(
    activity_log_router,
    dependencies=protected,
)