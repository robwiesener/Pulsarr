from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates

from sqlmodel import Session

from src.db.database import get_session
from src.services.downloads_service import downloads_service

router = APIRouter()

templates = Jinja2Templates(
    directory="src/templates"
)


@router.get("/result-management")
def downloads(
    request: Request,
    session: Session = Depends(get_session),
):

    results = downloads_service.get_results(
        session=session,
    )

    return templates.TemplateResponse(
        request=request,
        name="downloads/index.html",
        context={
            "results": results,
        },
    )

