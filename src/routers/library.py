from typing import Optional

from fastapi import APIRouter, Depends, Request, Query
from fastapi.templating import Jinja2Templates
from fastapi.responses import FileResponse, Response
from sqlmodel import Session, select, func, or_
from pathlib import Path

from src.db.database import get_session
from src.models.library import Library


router = APIRouter()

templates = Jinja2Templates(
    directory="src/templates"
)

PER_PAGE_DEFAULT = 100

SORT_COLUMNS = {
    "title": Library.title,
    "author": Library.author,
    "uploaded": Library.uploaded_at,
}


@router.get("/library")
def library(
    request: Request,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=PER_PAGE_DEFAULT, ge=10, le=200),
    sort: str = Query(default="uploaded"),
    direction: str = Query(default="desc"),
    q: Optional[str] = Query(default=None),
    rating: str = Query(default="all"),
    session: Session = Depends(get_session),
):
    # Valideer sorteer-parameters
    if sort not in SORT_COLUMNS:
        sort = "uploaded"
    if direction not in ("asc", "desc"):
        direction = "desc"

    # Bouw filters op
    filters = []

    if q and q.strip():
        search_term = f"%{q.strip()}%"
        filters.append(
            or_(
                Library.title.ilike(search_term),
                Library.author.ilike(search_term),
                Library.series.ilike(search_term),
            )
        )

    if rating == "none":
        filters.append(
            or_(Library.rating.is_(None), Library.rating == 0)
        )
    elif rating in ("1", "2", "3", "4", "5"):
        lower = float(rating)
        upper = lower + 1.0
        filters.append(Library.rating >= lower)
        filters.append(Library.rating < upper)

    # Tel het aantal boeken dat overblijft na filters
    count_statement = select(func.count()).select_from(Library)
    for f in filters:
        count_statement = count_statement.where(f)
    total = session.exec(count_statement).one()

    total_pages = max(1, (total + per_page - 1) // per_page)
    if page > total_pages:
        page = total_pages

    offset = (page - 1) * per_page

    # Haal de boeken op
    statement = select(Library)
    for f in filters:
        statement = statement.where(f)

    order_column = SORT_COLUMNS[sort]
    if direction == "asc":
        statement = statement.order_by(order_column.asc())
    else:
        statement = statement.order_by(order_column.desc())

    statement = statement.offset(offset).limit(per_page)

    books = session.exec(statement).all()

    return templates.TemplateResponse(
        request=request,
        name="library/index.html",
        context={
            "books": books,
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
            "sort": sort,
            "direction": direction,
            "q": q or "",
            "rating": rating,
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