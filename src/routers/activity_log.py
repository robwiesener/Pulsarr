from zoneinfo import ZoneInfo
from datetime import timezone

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select


from src.db.database import get_session
from src.models.activity_log import ActivityLog
from src.services.activity_log_service import activity_log_service


router = APIRouter()

templates = Jinja2Templates(
    directory="src/templates"
)


def to_local_time(value):
    return value.replace(
        tzinfo=timezone.utc
    ).astimezone(
        ZoneInfo("Europe/Amsterdam")
    )

@router.get("/activity-log")
def activity_log(
    request: Request,
    session: Session = Depends(get_session),
):
    logs = session.exec(
        select(ActivityLog)
        .order_by(ActivityLog.created_at.desc())
    ).all()

    return templates.TemplateResponse(
        request=request,
        name="activity_log/index.html",
        context={
            "logs": logs,
            "to_local_time": to_local_time,
        },
    )

@router.post("/activity-log/clear")
def clear_activity_log(
    session: Session = Depends(get_session),
):
    activity_log_service.clear(session)

    return RedirectResponse(
        url="/activity-log",
        status_code=303,
    )
