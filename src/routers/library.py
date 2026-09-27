from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import FileResponse, Response
from sqlmodel import Session, select
from pathlib import Path

from src.db.database import get_session
from src.models.library import Library


router = APIRouter()

templates = Jinja2Templates(
    directory="src/templates"
)


@router.get("/library")
def library(
    request: Request,
    session: Session = Depends(get_session),
):
    books = session.exec(
        select(Library)
        .order_by(Library.title)
    ).all()

    return templates.TemplateResponse(
        request=request,
        name="library/index.html",
        context={
            "books": books,
        },
    )


@router.get("/library/cover/{book_id}")
def library_cover(
    book_id: int,
    session: Session = Depends(get_session),
):
    book = session.get(
        Library,
        book_id,
    )

    if not book or not book.local_cover_path:
        return Response(
            status_code=404
        )

    cover_path = Path(
        book.local_cover_path
    )

    if not cover_path.is_file():
        return Response(
            status_code=404
        )

    return FileResponse(
        path=cover_path,
        media_type="image/jpeg",
    )