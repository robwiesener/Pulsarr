"""
Pulsarr - Wishlist Router

This module defines all HTTP routes for the Wishlist.

Responsibilities
----------------
- Display the wishlist
- Sort books
- Filter books by status
- Create new books
- Edit existing books
- Delete books

This module does NOT contain any database logic.
All database operations are delegated to wishlist_service.py.

Architecture
------------
Browser
    ↓
Wishlist Router
    ↓
Wishlist Service
    ↓
SQLModel
    ↓
SQLite database
"""

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Query
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from sqlmodel import Session, select, func

from src.models.book import Book
from src.models.enums import Status
from src.db.database import get_session
from src.services.wishlist_service import wishlist_service
from src.services.background_service import background_service

router = APIRouter()

templates = Jinja2Templates(
    directory="src/templates"
)

@router.get("/")
def books(
    request: Request,
    sort: str = Query(default="title"),
    status: str | None = Query(default=None),
    session: Session = Depends(get_session),
):

    books = wishlist_service.get_books(
        session=session,
        sort=sort,
        status=status,
    )

    return templates.TemplateResponse(
        request=request,
        name="wishlist/index.html",
        context={
            "books": books,
            "sort": sort,
            "status": status,
            "statuses": Status,
        },
    )

@router.post("/wishlist/search")
async def search_wishlist():

    await background_service.manual_wishlist_search()

    return RedirectResponse(
        url="/",
        status_code=303,
    )

@router.post("/wishlist/{book_id}/search/title")
def search_book_title(
    book_id: int,
    session: Session = Depends(get_session),
):

    wishlist_service.search_book(
        session=session,
        book_id=book_id,
        search_type="title",
    )

    return RedirectResponse(
        url="/",
        status_code=303,
    )


@router.post("/wishlist/{book_id}/search/author")
def search_book_author(
    book_id: int,
    session: Session = Depends(get_session),
):

    wishlist_service.search_book(
        session=session,
        book_id=book_id,
        search_type="author",
    )

    return RedirectResponse(
        url="/",
        status_code=303,
    )

@router.post("/wishlist/{book_id}/search/book")
def search_book_full(
    book_id: int,
    session: Session = Depends(get_session),
):

    wishlist_service.search_book_full(
        session=session,
        book_id=book_id,
    )

    return RedirectResponse(
        url="/",
        status_code=303,
    )

@router.get("/wishlist/add_book")
def add_book(
    request: Request,
    author: str = "",
):
    return templates.TemplateResponse(
        request=request,
        name="wishlist/form.html",
        context={
            "book": None,
            "author": author,
            "page_title": "Add Book",
            "statuses": list(Status),
        },
    )

@router.get("/wishlist/{book_id}/edit")
def edit_book(
    book_id: int,
    request: Request,
    session: Session = Depends(get_session),
):

    book = wishlist_service.get_book(session, book_id)

    return templates.TemplateResponse(
        request=request,
        name="wishlist/form.html",
        context={
            "page_title": "Edit book",
            "book": book,
            "statuses": Status,
        },
    )

@router.post("/wishlist/{book_id}/edit")
def update_book(
    book_id: int,
    title: str = Form(...),
    author: str = Form(...),
    status: str = Form(...),
    session: Session = Depends(get_session),
):

    book = wishlist_service.get_book(session, book_id)

    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    book.title = title
    book.author = author
    book.status = Status[status]

    wishlist_service.update_book(session, book)

    wishlist_service.search_book_full(
        session=session,
        book_id=book.id,
    )

    return RedirectResponse("/", status_code=303)

@router.post("/wishlist/{book_id}/delete")
def delete_book(
    book_id: int,
    session: Session = Depends(get_session),
):

    book = wishlist_service.get_book(session, book_id)

    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    wishlist_service.delete_book(session, book)

    return RedirectResponse("/", status_code=303)

@router.post("/books")
def create_book(
    title: str = Form(...),
    author: str = Form(...),
    status: str = Form(...),
    session: Session = Depends(get_session),
):

    book = Book(
        title=title,
        author=author,
        status=Status[status],
    )

    wishlist_service.add_book(session, book)

    wishlist_service.search_book_full(
        session=session,
        book_id=book.id,
    )

    return RedirectResponse(
        url="/",
        status_code=303,
    )