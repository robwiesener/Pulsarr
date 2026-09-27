from sqlmodel import Session, select

from src.models.library import Library
from src.services.calibre_service import calibre_service
from src.services.library_storage_service import (
    library_storage_service,
)


class LibraryService:

    def sync(
        self,
        session: Session,
    ) -> int:

        calibre_books = calibre_service.get_books()

        calibre_ids = {
            book["calibre_id"]
            for book in calibre_books
        }

        existing_books = session.exec(
            select(Library)
        ).all()

        existing_by_calibre_id = {
            book.calibre_id: book
            for book in existing_books
        }

        new_books = 0
        updated_books = 0
        deleted_books = 0
        synced_covers = 0
        failed_covers = 0

        for data in calibre_books:

            calibre_id = data["calibre_id"]

            existing = existing_by_calibre_id.get(
                calibre_id
            )

            if existing:

                book = existing

                book.title = data["title"]
                book.author = data["author"]
                book.series = data["series"]
                book.series_index = data["series_index"]
                book.description = data["description"]
                book.rating = data["rating"]
                book.uploaded_at = data["uploaded_at"]
                book.cover_url = data["cover_url"]
                book.epub_url = data["epub_url"]
                book.epub_size = data["epub_size"]
                book.epub_mtime = data["epub_mtime"]

                session.add(book)

                updated_books += 1

            else:

                book = Library(
                    calibre_id=calibre_id,
                    title=data["title"],
                    author=data["author"],
                    series=data["series"],
                    series_index=data["series_index"],
                    description=data["description"],
                    rating=data["rating"],
                    uploaded_at=data["uploaded_at"],
                    cover_url=data["cover_url"],
                    epub_url=data["epub_url"],
                    epub_size=data["epub_size"],
                    epub_mtime=data["epub_mtime"],
                )

                session.add(book)

                # We hebben het database-ID nodig voordat
                # we eventuele bestanden kunnen opslaan.
                session.flush()

                new_books += 1

            # Synchroniseer de cover.
            if self.sync_book_cover(book):

                synced_covers += 1

            else:

                failed_covers += 1

        for existing in existing_books:

            if existing.calibre_id not in calibre_ids:

                session.delete(existing)

                deleted_books += 1

        session.commit()

        print(
            "LIBRARY SERVICE: sync complete - "
            f"new={new_books}, "
            f"updated={updated_books}, "
            f"deleted={deleted_books}, "
            f"covers={synced_covers}, "
            f"cover_failures={failed_covers}"
        )

        return new_books

    def sync_book_cover(
        self,
        book: Library,
    ) -> bool:

        if not book.cover_url:

            print(
                "LIBRARY SERVICE: no cover URL - "
                f"{book.title}"
            )

            return False

        calibre_book_id = (
            self._extract_calibre_book_id(
                book.cover_url
            )
        )

        if calibre_book_id is None:

            print(
                "LIBRARY SERVICE: could not determine "
                f"Calibre book ID - {book.title}"
            )

            return False

        print(
            "LIBRARY SERVICE: syncing cover - "
            f"{book.title} "
            f"(Calibre ID {calibre_book_id})"
        )

        cover_path = (
            library_storage_service.download_cover(
                calibre_book_id=calibre_book_id,
                url=book.cover_url,
            )
        )

        if cover_path is None:

            return False

        book.local_cover_path = str(
            cover_path
        )

        return True

    def _extract_calibre_book_id(
        self,
        url: str,
    ) -> int | None:

        import re

        match = re.search(
            r"/get/cover/(\d+)/",
            url,
        )

        if not match:

            return None

        try:

            return int(
                match.group(1)
            )

        except ValueError:

            return None


library_service = LibraryService()