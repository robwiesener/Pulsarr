from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import RedirectResponse

from sqlmodel import Session

from app.db.database import get_session
from app.services.downloads_service import downloads_service
from app.templates import templates

router = APIRouter()



@router.get("/result-management")
def result_management(
    request: Request,
    session: Session = Depends(get_session),
):

    results = downloads_service.get_results(
        session=session,
    )

    return templates.TemplateResponse(
        request=request,
        name="result_management.html",
        context={
            "results": results,
        },
    )

@router.post("/result-management/delete")
def delete_results(
    record_ids: list[int] = Form(...),
    session: Session = Depends(get_session),
):

    downloads_service.delete_results(
        session=session,
        record_ids=record_ids,
    )

    return RedirectResponse(
        url="/result-management",
        status_code=303,
    )


@router.post("/result-management/download")
def download_results(
    record_ids: list[int] = Form(...),
    session: Session = Depends(get_session),
):

    print(
        f"RESULT MANAGEMENT ROUTE: bulk downloading "
        f"{record_ids}"
    )

    downloads_service.download_results(
        session=session,
        record_ids=record_ids,
    )

    return RedirectResponse(
        url="/result-management",
        status_code=303,
    )

@router.get("/result-management/test-status/{record_id}")
def test_download_status(
    record_id: int,
    session: Session = Depends(get_session),
):
    downloads_service.check_download_status(
        session=session,
        record_id=record_id,
    )

    return RedirectResponse(
        url="/result-management",
        status_code=303,
    )
