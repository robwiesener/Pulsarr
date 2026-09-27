import asyncio

from sqlmodel import Session, select

from src.config.config_service import config_service
from src.db.database import engine
from src.models.enums import DownloadStatus, Status
from src.models.search_result_record import SearchResultRecord
from src.services.downloads_service import downloads_service
from src.services.wishlist_service import wishlist_service
from src.services.activity_log_service import activity_log_service

class BackgroundService:

    def __init__(self):
        self.download_status_task = None
        self.wishlist_search_task = None
        self.manual_wishlist_search_task = None
        self.wishlist_search_lock = asyncio.Lock()

    async def start(self):

        self.download_status_task = asyncio.create_task(
            self.download_status_worker()
        )

        self.wishlist_search_task = asyncio.create_task(
            self.wishlist_search_worker()
        )

        print("BACKGROUND SERVICE: Download, and Wislist background workers started")

    async def stop(self):

        tasks = [
            self.download_status_task,
            self.wishlist_search_task,
            self.manual_wishlist_search_task,
        ]

        tasks = [
            task
            for task in tasks
            if task is not None
        ]

        for task in tasks:

            if not task.done():
                task.cancel()

        await asyncio.gather(
            *tasks,
            return_exceptions=True,
        )


    async def download_status_worker(self):

        while True:

            settings = config_service.load()

            interval = (
                settings.background.download_status_interval
            )

            print(f"BACKGROUND SERVICE: Download status worker sleeping for {interval} seconds")

            await asyncio.sleep(interval)

            with Session(engine) as session:

                records = session.exec(
                    select(SearchResultRecord)
                    .where(
                        SearchResultRecord.download_status
                        == DownloadStatus.DOWNLOADING
                    )
                ).all()

                print(f"BACKGROUND SERVICE: found {len(records)} downloading record(s)")

                for record in records:

                    print(
                        "BACKGROUND SERVICE: checking record "
                        f"{record.id}, "
                        f"book_id={record.book_id}, "
                        f"download_status={record.download_status}"
                    )

                    result = downloads_service.check_download_status(
                        session=session,
                        record_id=record.id,
                    )

                    print(
                        "BACKGROUND SERVICE: check result "
                        f"record {record.id}: {result}"
                    )

                if not records:
                    continue

                print(
                    "BACKGROUND SERVICE: checking "
                    f"{len(records)} download(s)"
                )


    async def manual_wishlist_search(self):

        if (
            self.manual_wishlist_search_task
            and not self.manual_wishlist_search_task.done()
        ):
            print(
                "BACKGROUND SERVICE: Manual wishlist search "
                "already running"
            )
            return

        async def run_search():

            async with self.wishlist_search_lock:

                print(
                    "BACKGROUND SERVICE: Manual wishlist search started"
                )

                def search():

                    with Session(engine) as session:
                        wishlist_service.search_books(session)

                try:

                    await asyncio.to_thread(search)

                    print(
                        "BACKGROUND SERVICE: Manual wishlist search finished"
                    )

                except Exception as exc:
                    print(
                        "BACKGROUND SERVICE: Manual wishlist search failed: "
                        f"{exc}"
                    )

                    with Session(engine) as session:
                        activity_log_service.log(
                            session=session,
                            level="ERROR",
                            source="BackgroundTask",
                            message="Manual Search Failed",
                            details=str(exc),
                        )

        self.manual_wishlist_search_task = asyncio.create_task(
            run_search()
        )


    async def wishlist_search_worker(self):

        first_run = True

        while True:

            settings = config_service.load()
            interval = (settings.background.wishlist_search_interval)

            if first_run:
                print(f"BACKGROUND SERVICE: Wishlist search worker initial run")
                first_run = False
            else:
                print(f"BACKGROUND SERVICE: Wishlist search worker sleeping {interval} seconds")
                
                await asyncio.sleep(interval)

                print("BACKGROUND SERVICE: Wishlist search worker triggered")

            async with self.wishlist_search_lock:

                print(
                    "BACKGROUND SERVICE: Automatic wishlist search started"
                )

                def search():
                    with Session(engine) as session:
                        new_records = wishlist_service.search_books(
                            session
                        )

                        activity_log_service.log_background_task(
                            session=session,
                            message="Automatic Search Completed",
                            details=f"{new_records} new result(s)",
                        )

                try:

                    await asyncio.to_thread(search)

                    print(
                        "BACKGROUND SERVICE: Automatic wishlist search finished"
                    )

                except Exception as exc:

                    print(
                        "BACKGROUND SERVICE: Automatic wishlist search failed: "
                        f"{exc}"
                    )

                    with Session(engine) as session:
                        activity_log_service.log(
                            session=session,
                            level="ERROR",
                            source="BackgroundTask",
                            message="Automatic Search Failed",
                            details=str(exc),
                        )

background_service = BackgroundService()
