from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends
from fastapi.staticfiles import StaticFiles

import src.models

from src.screens.wishlist.router import router as wishlist_router
from src.screens.configuration.router import router as settings_router
from src.screens.result_management.router import router as result_management_router
from src.screens.library.router import router as library_router
from src.screens.activity_log.router import router as activity_log_router

from src.cloudflare import validate_cloudflare

from src.db.database import create_db_and_tables

from src.services.background_service import background_service


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
    StaticFiles(directory="src/static"),
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