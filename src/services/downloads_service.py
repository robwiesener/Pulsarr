from sqlmodel import Session, select

from src.models.book import Book
from src.models.enums import Status, SearchType, DownloadStatus
from src.models.search_result_record import SearchResultRecord
from src.services.sabnzbd_service import sabnzbd_service


class DownloadsService:

    def get_results(self, session: Session):

        statement = (
            select(SearchResultRecord)
            .order_by(SearchResultRecord.id.desc())
        )

        return session.exec(statement).all()

    def delete_results(
        self,
        session: Session,
        record_ids: list[int],
    ):

        if not record_ids:
            print("DOWNLOADS SERVICE: no records selected")
            return

        records = session.exec(
            select(SearchResultRecord)
            .where(SearchResultRecord.id.in_(record_ids))
        ).all()

        affected_book_ids = {
            record.book_id
            for record in records
            if record.book_id is not None
        }

        for record in records:
            session.delete(record)

        session.flush()

        for book_id in affected_book_ids:

            remaining_result = session.exec(
                select(SearchResultRecord)
                .where(
                    SearchResultRecord.book_id == book_id
                )
            ).first()

            if remaining_result is None:

                book = session.get(Book, book_id)

                if book:
                    book.status = Status.UNAVAILABLE
                    session.add(book)

        session.commit()

        print(
            f"DOWNLOADS SERVICE: deleted "
            f"{len(records)} result(s)"
        )

    def download_results(
        self,
        session: Session,
        record_ids: list[int],
    ):

        if not record_ids:
            return

        records = session.exec(
            select(SearchResultRecord)
            .where(SearchResultRecord.id.in_(record_ids))
        ).all()

        for record in records:

            success, message, nzo_id = sabnzbd_service.add_url(
                record.download_url
            )

            print(
                f"SABnzbd result for record {record.id}: "
                f"{success} - {message}"
            )

            if not success:

                record.download_status = DownloadStatus.DOWNLOAD_FAILED

                # Alleen een gekoppeld Wishlist-boek aanpassen.
                if record.book_id is not None:

                    book = session.get(Book, record.book_id)

                    if book:
                        book.status = Status.DOWNLOAD_FAILED
                        session.add(book)

                session.add(record)

                continue

            record.sabnzbd_id = nzo_id
            record.download_status = DownloadStatus.DOWNLOADING

            session.add(record)

            # Een TITLE/AUTHOR zoekresultaat heeft geen book_id.
            # Daardoor blijft zo'n zoekopdracht volledig los van Wishlist.
            if record.book_id is not None:

                book = session.get(Book, record.book_id)

                if book:

                    book.status = Status.DOWNLOADING
                    session.add(book)

        session.commit()

        print(
            f"DOWNLOADS SERVICE: processed "
            f"{len(records)} records"
        )

    def check_download_status(
        self,
        session: Session,
        record_id: int,
    ):

        record = session.get(SearchResultRecord, record_id)

        if not record:
            print(
                f"DOWNLOADS SERVICE: record {record_id} not found"
            )
            return

        if not record.sabnzbd_id:
            print(
                f"DOWNLOADS SERVICE: record {record_id} "
                "has no SABnzbd ID"
            )
            return

        success, status, message = (
            sabnzbd_service.get_download_status(
                record.sabnzbd_id
            )
        )

        if not success:

            record.download_status = (
                DownloadStatus.DOWNLOAD_FAILED
            )

            # Alleen gekoppelde Wishlist-boeken aanpassen.
            if record.book_id is not None:

                book = session.get(
                    Book,
                    record.book_id,
                )

                if book:
                    book.status = Status.DOWNLOAD_FAILED
                    session.add(book)

            session.add(record)
            session.commit()

            return False, message

        print(
            f"SABnzbd queue status for record "
            f"{record.id}: {status}"
        )

        if status == DownloadStatus.DOWNLOADING:

            record.download_status = (
                DownloadStatus.DOWNLOADING
            )

            if record.book_id is not None:

                book = session.get(
                    Book,
                    record.book_id,
                )

                if book:
                    book.status = Status.DOWNLOADING
                    session.add(book)

        elif status == DownloadStatus.DOWNLOADED:

            record.download_status = (
                DownloadStatus.DOWNLOADED
            )

            if record.book_id is not None:

                book = session.get(
                    Book,
                    record.book_id,
                )

                if book:
                    book.status = Status.DOWNLOADED
                    session.add(book)

        session.add(record)
        session.commit()

        return True, status


downloads_service = DownloadsService()