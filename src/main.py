from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

import src.models

from src.routers.wishlist import router as wishlist_router
from src.routers.settings import router as settings_router
from src.routers.result_management import router as result_management_router
from src.routers.library import router as library_router
from src.routers.activity_log import router as activity_log_router

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


app.include_router(wishlist_router)
app.include_router(settings_router)
app.include_router(result_management_router)
app.include_router(library_router)
app.include_router(activity_log_router)
