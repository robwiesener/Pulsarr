from fastapi import APIRouter, Depends, Request, Query
from fastapi.templating import Jinja2Templates
from fastapi.responses import FileResponse, Response
from sqlmodel import Session, select, func
from pathlib import Path

from src.db.database import get_session
from src.models.library import Library


router = APIRouter()

templates = Jinja2Templates(
    directory="src/templates"
)

PER_PAGE_DEFAULT = 50


@router.get("/library")
def library(
    request: Request,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=PER_PAGE_DEFAULT, ge=10, le=200),
    session: Session = Depends(get_session),
):
    total = session.exec(
        select(func.count()).select_from(Library)
    ).one()

    total_pages = max(1, (total + per_page - 1) // per_page)

    if page > total_pages:
        page = total_pages

    offset = (page - 1) * per_page

    books = session.exec(
        select(Library)
        .order_by(Library.title)
        .offset(offset)
        .limit(per_page)
    ).all()

    return templates.TemplateResponse(
        request=request,
        name="library/index.html",
        context={
            "books": books,
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
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