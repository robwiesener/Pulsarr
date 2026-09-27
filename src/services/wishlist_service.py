"""
Pulsarr - Wishlist Service

This module contains the business logic for the Wishlist.

Responsibilities
----------------
- Retrieve books from the database
- Apply sorting
- Apply filtering
- Create, update and delete books
- Search for books, titles and authors

The router should never execute SQL directly.
All database interaction belongs in this service.
"""
import re

from sqlmodel import Session, select, func

from src.models.enums import Status, SearchType, DownloadStatus
from src.models.book import Book
from src.models.search_result_record import SearchResultRecord
from src.services.spotweb_service import spotweb_service

from src.services.bookmatch_service import (
    book_matches,
    match_title_or_author,
)

from src.config.config_service import config_service
from src.services.activity_log_service import activity_log_service


class BookService:

    def _log(
        self,
        session: Session,
        level: str,
        message: str,
        details: str | None = None,
    ) -> None:
        activity_log_service.log(
            session=session,
            level=level,
            source="WishlistService",
            message=message,
            details=details,
        )

    def get_book(
        self,
        session: Session,
        book_id: int,
    ) -> Book | None:

        statement = select(Book).where(Book.id == book_id)

        return session.exec(statement).first()


    def get_books(
        self,
        session: Session,
        sort: str = "title",
        status: str | None = None,
    ) -> list[Book]:

        statement = select(Book)

        if status:
            statement = statement.where(
                Book.status == Status[status]
            )

        if sort == "title":

            statement = statement.order_by(
                func.lower(Book.title),
                func.lower(Book.author),
            )

        elif sort == "author":

            statement = statement.order_by(
                func.lower(Book.author),
                func.lower(Book.title),
            )

        return session.exec(statement).all()



    

    def add_book(
        self,
        session: Session,
        book: Book,
    ) -> Book:

        session.add(book)
        session.commit()
        session.refresh(book)

        return book

    def update_book(
        self,
        session: Session,
        book: Book,
    ) -> Book:

        session.add(book)
        session.commit()
        session.refresh(book)

        return book

    def delete_book(
        self,
        session: Session,
        book: Book,
    ) -> None:

        session.delete(book)
        session.commit()

    def search_books(
        self,
        session: Session,
    ) -> int:

        statement = (
            select(Book)
            .where(Book.status == Status.UNAVAILABLE)
        )

        books = session.exec(statement).all()

        print(
            "WISHLIST SERVICE: "
            f"Books with status UNAVAILABLE: {len(books)}"
        )

        if not books:
            print(
                "WISHLIST SERVICE: "
                "No unavailable books"
            )
            return 0

        settings = config_service.load()

        description_search_keywords = [
            keyword.strip().lower()
            for keyword in (
                settings.wishlist.description_search_keywords
                .split(",")
            )
            if keyword.strip()
        ]

        print(
            "WISHLIST SERVICE: "
            f"Description search keywords: "
            f"{description_search_keywords}"
        )

        print(
            "WISHLIST SERVICE: "
            "Fetching recent releases from Spotweb"
        )

        try:
            results = spotweb_service.fetch_recent_books_paginated(
                pages=3,
                page_size=100,
            )

        except Exception as exc:
            self._log(
                session,
                "ERROR",
                "Wishlist search failed while fetching Spotweb releases",
                str(exc),
            )

            print(
                "WISHLIST SERVICE: "
                f"Spotweb search failed: {exc}"
            )

            raise



        print(
            "WISHLIST SERVICE: "
            f"Spotweb returned {len(results)} releases"
        )

        new_records = 0

        for book in books:

            matched_results = []

            for result in results:

                spot_title = result.title or ""

                # --------------------------------------------------
                # 1. Eerst altijd de Spot-titel controleren.
                #
                # Als titel + auteur in de Spot-titel staan,
                # is dit direct een normale match.
                # --------------------------------------------------

                details = None

                if book_matches(
                    book.title,
                    book.author,
                    spot_title,
                    "",
                ):
                    matched_results.append(result)
                    continue

                # --------------------------------------------------
                # 2. Alleen bij een geconfigureerd package keyword
                #    zoeken we verder in de description.
                # --------------------------------------------------

                normalized_spot_title = spot_title.lower()

                is_description_search = any(
                    keyword in normalized_spot_title
                    for keyword in description_search_keywords
                )

                if not is_description_search:
                    continue

                print(
                    "WISHLIST SERVICE: "
                    f"Fetching details for: {result.title}"
                )

                details = spotweb_service.get_details(
                    result.guid
                )

                if not details:
                    continue

                if book_matches(
                    book.title,
                    book.author,
                    spot_title,
                    details.description or "",
                ):
                    matched_results.append(result)

            print(
                "WISHLIST SERVICE: "
                f"{book.title} - {book.author}: "
                f"{len(matched_results)} matching Spotweb result(s)"
            )

            for result in matched_results:

                existing = session.exec(
                    select(SearchResultRecord)
                    .where(
                        SearchResultRecord.book_id == book.id,
                        SearchResultRecord.guid == result.guid,
                        SearchResultRecord.search_type == SearchType.BOOK,
                    )
                ).first()

                if existing:
                    continue

                record = SearchResultRecord(
                    book_id=book.id,
                    search_title=book.title,
                    search_author=book.author,
                    guid=result.guid,

                    # Altijd de Spot-titel tonen.
                    description=result.title,

                    download_url=result.download_url,
                    size=result.size,
                    age=0,
                    category=result.category,
                    search_type=SearchType.BOOK,
                    download_status=DownloadStatus.POSSIBLE_MATCH,
                )

                session.add(record)
                new_records += 1

            if matched_results:
                book.status = Status.POSSIBLE_MATCH
                session.add(book)

        session.commit()

        print(
            "WISHLIST SERVICE: "
            f"search_books() FINISHED, "
            f"created {new_records} new record(s)"
        )

        return new_records

    def count_books(
        self,
        session: Session,
    ) -> int:

        statement = select(Book)

        return len(
            session.exec(statement).all()
        )

    def _search_package_matches(
        self,
        book: Book,
        package_keywords: list[str],
        search_type: str = "full",
    ) -> list:

        matched_results = []
        seen_guids = set()

        for keyword in package_keywords:
            keyword = keyword.strip()

            if not keyword:
                continue

            print(
                "WISHLIST SERVICE: "
                f"Package search for keyword: {keyword!r}"
            )

            package_results = spotweb_service.search_books(
                keyword
            )

            print(
                "WISHLIST SERVICE: "
                f"Package search returned "
                f"{len(package_results)} result(s)"
            )

            for result in package_results:
                if result.guid in seen_guids:
                    continue

                seen_guids.add(result.guid)

                try:
                    details = spotweb_service.get_details(
                        result.guid
                    )
                except Exception as exc:
                    print(
                        "WISHLIST SERVICE: "
                        f"Package details search failed for "
                        f"{result.guid}: {exc}"
                    )
                    raise

                if not details:
                    continue

                if search_type == "full":
                    is_match = book_matches(
                        book.title,
                        book.author,
                        result.title,
                        details.description,
                    )
                else:
                    is_match = False

                    lines = re.split(
                        r"\<br\s\*/?>|\r?\n",
                        details.description or "",
                    )

                    for line in lines:
                        line = line.strip()

                        if not line:
                            continue

                        if match_title_or_author(
                            book.title,
                            book.author,
                            line,
                        ):
                            is_match = True
                            break

                if is_match:
                    print(
                        "WISHLIST SERVICE: "
                        f"Package match found: "
                        f"{result.title}"
                    )
                    matched_results.append(result)

        return matched_results

    def search_book_full(
        self,
        session: Session,
        book_id: int,
    ) -> None:

        print(
            f"WISHLIST SERVICE: search_book_full() "
            f"book={book_id}"
        )

        book = self.get_book(
            session=session,
            book_id=book_id,
        )

        if not book:
            print(
                f"WISHLIST SERVICE: Book {book_id} not found"
            )
            self._log(
                session,
                "WARNING",
                "Wishlist book not found",
                f"book_id={book_id}",
            )
            return

        print(
            "WISHLIST SERVICE: "
            f"Searching Spotweb for book: "
            f"{book.title} - {book.author}"
        )

        # --------------------------------------------------
        # 1. Title search
        # --------------------------------------------------

        try:
            title_results = spotweb_service.search_books(
                book.title
            )
        except Exception as exc:
            print(
                f"WISHLIST SERVICE: "
                f"Title search failed: {exc}"
            )
            self._log(
                session,
                "ERROR",
                "Full wishlist title search failed",
                f"book_id={book_id}, "
                f"query={book.title!r}: {exc}",
            )
            raise

        # --------------------------------------------------
        # 2. Author search
        # --------------------------------------------------

        try:
            author_results = spotweb_service.search_books(
                book.author
            )
        except Exception as exc:
            print(
                f"WISHLIST SERVICE: "
                f"Author search failed: {exc}"
            )
            self._log(
                session,
                "ERROR",
                "Full wishlist author search failed",
                f"book_id={book_id}, "
                f"query={book.author!r}: {exc}",
            )
            raise

        print(
            "WISHLIST SERVICE: "
            f"Title search returned "
            f"{len(title_results)} result(s)"
        )

        print(
            "WISHLIST SERVICE: "
            f"Author search returned "
            f"{len(author_results)} result(s)"
        )

        combined = {}

        for result in title_results:
            combined[result.guid] = result

        for result in author_results:
            combined[result.guid] = result

        matched_results = []

        # --------------------------------------------------
        # 3. Check direct title/author search results
        # --------------------------------------------------
        for result in combined.values():
            if book_matches(
                book.title,
                book.author,
                result.title,
                "",
            ):
                matched_results.append(result)

        # --------------------------------------------------
        # 4. If no direct match, search packages
        # --------------------------------------------------
        if not matched_results:
            settings = config_service.load()

            package_keywords = [
                keyword.strip()
                for keyword in (
                    settings.wishlist.description_search_keywords
                    .split(",")
                )
                if keyword.strip()
            ]

            print(
                "WISHLIST SERVICE: "
                "No direct match found, "
                f"searching packages with keywords: "
                f"{package_keywords}"
            )

            matched_results = self._search_package_matches(
                book=book,
                package_keywords=package_keywords,
            )

        print(
            "WISHLIST SERVICE: "
            f"Book search found "
            f"{len(matched_results)} matching result(s)"
        )

        new_records = 0

        for result in matched_results:

            existing = session.exec(
                select(SearchResultRecord)
                .where(
                    SearchResultRecord.book_id == book.id,
                    SearchResultRecord.guid == result.guid,
                    SearchResultRecord.search_type == SearchType.BOOK,
                )
            ).first()

            if existing:
                continue

            record = SearchResultRecord(
                book_id=book.id,
                search_title=book.title,
                search_author=book.author,
                guid=result.guid,
                description=result.title,
                download_url=result.download_url,
                size=result.size,
                age=0,
                category=result.category,
                search_type=SearchType.BOOK,
                download_status=DownloadStatus.POSSIBLE_MATCH,
            )

            session.add(record)
            new_records += 1

        if matched_results:
            book.status = Status.POSSIBLE_MATCH
            session.add(book)

        session.commit()

        print(
            "WISHLIST SERVICE: "
            f"search_book_full() FINISHED, "
            f"created {new_records} new record(s)"
        )

    def search_book(
        self,
        session: Session,
        book_id: int,
        search_type: str,
    ) -> None:

        print(
            f"WISHLIST SERVICE: search_book() "
            f"book={book_id}, type={search_type}"
        )

        book = self.get_book(
            session=session,
            book_id=book_id,
        )

        if not book:
            print(
                f"WISHLIST SERVICE: Book {book_id} not found"
            )
            return

        if search_type == "title":

            query = book.title
            record_search_type = SearchType.TITLE
            search_title = book.title
            search_author = None

        elif search_type == "author":

            query = book.author
            record_search_type = SearchType.AUTHOR
            search_title = None
            search_author = book.author

        else:
            print(
                f"WISHLIST SERVICE: Unknown search type: "
                f"{search_type}"
            )
            self._log(
                session,
                "WARNING",
                "Unknown wishlist search type",
                f"search_type={search_type!r}, book_id={book_id}",
            )
            return

        print(
            f"WISHLIST SERVICE: Searching Spotweb for: "
            f"{query}"
        )

        try:
            results = spotweb_service.search_books(query)
        except Exception as exc:
            print(
                f"WISHLIST SERVICE: Spotweb search failed: {exc}"
            )
            self._log(
                session,
                "ERROR",
                "Wishlist Spotweb search failed",
                f"book_id={book_id}, search_type={search_type}, "
                f"query={query!r}: {exc}",
            )
            raise

        print(
            f"WISHLIST SERVICE: Found {len(results)} results "
            f"for: {query}"
        )

        settings = config_service.load()

        package_keywords = [
            keyword.strip()
            for keyword in (
                settings.wishlist.description_search_keywords
                .split(",")
            )
            if keyword.strip()
        ]

        print(
            "WISHLIST SERVICE: "
            f"Searching packages in addition to direct "
            f"{search_type} search with keywords: "
            f"{package_keywords}"
        )

        package_matches = self._search_package_matches(
            book=book,
            package_keywords=package_keywords,
            search_type=search_type,
        )

        results_by_guid = {
            result.guid: result
            for result in results
        }

        for result in package_matches:
            results_by_guid[result.guid] = result

        results = list(results_by_guid.values())

        self._log(
            session,
            "INFO",
            "Wishlist Spotweb search completed",
            f"book_id={book_id}, search_type={search_type}, "
            f"query={query!r}, results={len(results)}",
        )

        new_records = 0

        for result in results:

            existing = session.exec(
                select(SearchResultRecord)
                .where(
                    SearchResultRecord.book_id.is_(None),
                    SearchResultRecord.guid == result.guid,
                    SearchResultRecord.search_type == record_search_type,
                    SearchResultRecord.search_title == search_title,
                    SearchResultRecord.search_author == search_author,
                )
            ).first()

            if existing:
                continue

            record = SearchResultRecord(

                # TITLE/AUTHOR searches zijn niet gekoppeld
                # aan het Wishlist-boek.
                book_id=None,

                search_title=search_title,
                search_author=search_author,

                guid=result.guid,
                description=result.title,
                download_url=result.download_url,
                size=result.size,
                age=0,
                category=result.category,

                search_type=record_search_type,

                download_status=DownloadStatus.POSSIBLE_MATCH,
            )

            session.add(record)
            new_records += 1

        # Geen wijziging aan book.status!
        #
        # Een TITLE/AUTHOR search is alleen een losse zoekopdracht
        # en mag de status van het Wishlist-boek niet beïnvloeden.

        session.commit()

        print(
            f"WISHLIST SERVICE: New records for "
            f"{search_type} search: {new_records}"
        )

wishlist_service = BookService()