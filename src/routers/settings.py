from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from sqlmodel import Session, select

from src.config.config_service import config_service
from src.services.spotweb_service import spotweb_service
from src.services.sabnzbd_service import sabnzbd_service
from src.db.database import get_session
from src.models.library import Library
from src.services.calibre_service import calibre_service
from src.services.library_service import library_service

router = APIRouter()

templates = Jinja2Templates(directory="src/templates")


@router.get("/configuration")
def settings(
    request: Request,
    session: Session = Depends(get_session),
):

    settings = config_service.load()

    book_count = len(
        session.exec(
            select(Library)
        ).all()
    )

    return templates.TemplateResponse(
        request=request,
        name="configuration/index.html",
        context={
            "settings": settings,
            "book_count": book_count,
            "calibre_url": calibre_service.get_base_url(),
        },
    )

@router.post("/configuration")
def save_settings(
    request: Request,

    session: Session = Depends(get_session),

    spotweb_url: str = Form(...),
    spotweb_api_key: str = Form(...),

    sabnzbd_url: str = Form(...),
    sabnzbd_api_key: str = Form(...),
    sabnzbd_category: str = Form(...),

    download_status_interval: int = Form(...),
    wishlist_search_interval: int = Form(...),
    description_search_keywords: str = Form(...),
    calibre_url: str = Form(...),

    action: str = Form(...),
):

    settings = config_service.load()

    # Calibre settings
    settings.calibre.url = calibre_url

    # Spotweb settings
    settings.spotweb.url = spotweb_url
    settings.spotweb.api_key = spotweb_api_key

    # SABnzbd settings
    settings.sabnzbd.url = sabnzbd_url
    settings.sabnzbd.api_key = sabnzbd_api_key
    settings.sabnzbd.category = sabnzbd_category

    # Background settings
    settings.background.download_status_interval = (
        download_status_interval
    )
    settings.background.wishlist_search_interval = (
        wishlist_search_interval
    )

    # Wishlist settings
    settings.wishlist.description_search_keywords = (
        description_search_keywords
    )

    if action == "save_calibre":

        config_service.save(settings)

        return RedirectResponse(
            "/configuration",
            status_code=303,
        )

    if action == "save_spotweb":

        config_service.save(settings)

        return RedirectResponse(
            "/configuration",
            status_code=303,
        )

    if action == "test_spotweb":

        config_service.save(settings)

        success, message = (
            spotweb_service.test_connection()
        )

        return templates.TemplateResponse(
            request=request,
            name="configuration/index.html",
            context={
                "settings": settings,
                "book_count": len(
                    session.exec(
                        select(Library)
                    ).all()
                ),
                "calibre_url": calibre_service.get_base_url(),
                "test_spotweb_success": success,
                "test_spotweb_message": message,
            },
        )

    if action == "save_sabnzbd":

        config_service.save(settings)

        return RedirectResponse(
            "/configuration",
            status_code=303,
        )

    if action == "save_background":

        config_service.save(settings)

        return RedirectResponse(
            "/configuration",
            status_code=303,
        )

    if action == "save_wishlist":

        config_service.save(settings)

        return RedirectResponse(
            "/configuration",
            status_code=303,
        )

    if action == "test_sabnzbd":

        config_service.save(settings)

        success, message = (
            sabnzbd_service.test_connection()
        )

        return templates.TemplateResponse(
            request=request,
            name="configuration/index.html",
            context={
                "settings": settings,
                "test_success": success,
                "test_message": message,
            },
        )

    if action == "test_calibre":

        config_service.save(settings)

        try:

            books = calibre_service.get_books()

            success = True

            message = (
                f"Connection successful. "
                f"Found {len(books)} books in Calibre."
            )

        except Exception as error:

            success = False

            message = (
                f"Connection failed: {error}"
            )

        book_count = len(
            session.exec(
                select(Library)
            ).all()
        )

        return templates.TemplateResponse(
            request=request,
            name="configuration/index.html",
            context={
                "settings": settings,
                "book_count": book_count,
                "calibre_url": calibre_service.get_base_url(),
                "test_calibre_success": success,
                "test_calibre_message": message,
            },
        )

    if action == "sync_calibre":

        config_service.save(settings)

        try:

            library_service.sync(
                session
            )

            success = True

            message = (
                "Library sync completed successfully."
            )

        except Exception as error:

            success = False

            message = (
                f"Library sync failed: {error}"
            )

        book_count = len(
            session.exec(
                select(Library)
            ).all()
        )

        return templates.TemplateResponse(
            request=request,
            name="configuration/index.html",
            context={
                "settings": settings,
                "book_count": book_count,
                "calibre_url": calibre_service.get_base_url(),
                "sync_calibre_success": success,
                "sync_calibre_message": message,
            },
        )