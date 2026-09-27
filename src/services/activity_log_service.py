from datetime import datetime, timezone

from sqlmodel import Session, select

from src.models.activity_log import ActivityLog


class ActivityLogService:

    def log(
        self,
        session: Session,
        level: str,
        source: str,
        message: str,
        details: str = "",
    ) -> ActivityLog:

        entry = ActivityLog(
            level=level,
            source=source,
            message=message,
            details=details,
        )

        session.add(entry)
        session.commit()
        session.refresh(entry)

        return entry

    def log_background_task(
        self,
        session: Session,
        message: str,
        details: str = "",
    ) -> ActivityLog:
        entry = None

        if message == "Automatic Search Completed":
            entry = session.exec(
                select(ActivityLog)
                .where(
                    ActivityLog.source == "BackgroundTask",
                    ActivityLog.message == "Automatic Search Completed",
                )
            ).first()

        if entry:
            entry.created_at = datetime.now(timezone.utc)
            entry.level = "INFO"
            entry.details = details
        else:
            entry = ActivityLog(
                level="INFO",
                source="BackgroundTask",
                message=message,
                details=details,
            )
            session.add(entry)

        session.commit()
        session.refresh(entry)
        return entry

    def clear(
        self,
        session: Session,
    ) -> None:

        logs = session.exec(
            select(ActivityLog)
        ).all()

        for log in logs:
            session.delete(log)

        session.commit()


activity_log_service = ActivityLogService()