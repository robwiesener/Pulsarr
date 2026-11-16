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

from app.db.database import create_db_and_tables

from app.services.background_service import background_service


@asynccontextmanager
async def lifespan(app: FastAPI):

    create_db_and_tables()

    await background_service.start()

    yield

    await background_service.stop()


app = FastAPI(
    title="Pulsarr",
    lifespan=lifespan,
)


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