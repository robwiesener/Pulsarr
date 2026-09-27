from datetime import datetime

import xml.etree.ElementTree as ET

import requests

from sqlmodel import Session

from src.config.config_service import config_service
from src.db.database import engine
from src.models.spotweb_result import SpotwebResult
from src.services.activity_log_service import activity_log_service


class SpotwebService:

    BOOK_CATEGORY = 7020

    def _get_api_url(self) -> str:
        settings = config_service.load()

        url = settings.spotweb.url.strip()

        if not url:
            raise ValueError(
                "Spotweb URL is not configured. "
                "Configure Spotweb under Configuration."
            )

        return url.rstrip("/") + "/api"

    def _log(
        self,
        level: str,
        message: str,
        details: str | None = None,
    ) -> None:
        with Session(engine) as session:
            activity_log_service.log(
                session=session,
                level=level,
                source="SpotwebService",
                message=message,
                details=details,
            )

    def test_connection(self) -> tuple[bool, str]:

        settings = config_service.load()

        params = {
            "t": "search",
            "cat": self.BOOK_CATEGORY,
            "offset": 0,
            "limit": 1,
            "apikey": settings.spotweb.api_key,
        }

        try:
            response = requests.get(
                self._get_api_url(),
                params=params,
                timeout=5,
            )

            response.raise_for_status()

            root = ET.fromstring(response.text)

            if root.find("./channel") is not None:
                return (
                    True,
                    "Spotweb connection test successful.",
                )

            return (
                False,
                "Spotweb connection failed.",
            )

        except Exception as exc:
            return False, str(exc)

    def fetch_recent_books(
        self,
        offset: int = 0,
        limit: int = 100,
    ) -> list[SpotwebResult]:

        settings = config_service.load()

        params = {
            "t": "search",
            "cat": self.BOOK_CATEGORY,
            "offset": offset,
            "limit": limit,
            "apikey": settings.spotweb.api_key,
        }

        try:
            response = requests.get(
                self._get_api_url(),
                params=params,
                timeout=30,
            )

            response.raise_for_status()

        except requests.RequestException as exc:
            message = (
                f"Recent books request failed "
                f"(offset={offset}, limit={limit})"
            )

            print(
                "SPOTWEB SERVICE: "
                f"{message}: {exc}"
            )

            self._log(
                level="ERROR",
                message=message,
                details=str(exc),
            )

            raise

        try:
            root = ET.fromstring(response.text)
        except ET.ParseError as exc:
            message = (
                f"Invalid XML response for recent books "
                f"(offset={offset}, limit={limit})"
            )

            print(
                "SPOTWEB SERVICE: "
                f"{message}: {exc}"
            )

            self._log(
                level="ERROR",
                message=message,
                details=str(exc),
            )

            raise

        return self._parse_results(root)

    def fetch_recent_books_paginated(
        self,
        pages: int = 10,
        page_size: int = 100,
    ) -> list[SpotwebResult]:

        results = []

        for page in range(pages):

            offset = page * page_size

            print(
                "SPOTWEB SERVICE: "
                f"Fetching page {page + 1}/{pages} "
                f"(offset={offset}, limit={page_size})"
            )

            page_results = self.fetch_recent_books(
                offset=offset,
                limit=page_size,
            )

            print(
                "SPOTWEB SERVICE: "
                f"Page {page + 1} returned "
                f"{len(page_results)} result(s)"
            )

            if not page_results:
                break

            results.extend(page_results)

            if len(page_results) < page_size:
                break

        print(
            "SPOTWEB SERVICE: "
            f"Pagination finished, total results: {len(results)}"
        )

        return results

    def search_books(
        self,
        query: str,
        limit: int = 100,
    ) -> list[SpotwebResult]:

        settings = config_service.load()

        params = {
            "t": "search",
            "q": query,
            "cat": self.BOOK_CATEGORY,
            "offset": 0,
            "limit": limit,
            "apikey": settings.spotweb.api_key,
        }

        try:
            response = requests.get(
                self._get_api_url(),
                params=params,
                timeout=30,
            )
            response.raise_for_status()

        except requests.RequestException as exc:
            print(
                "SPOTWEB SERVICE: "
                f"Book search request failed "
                f"(query={query!r}, limit={limit}): {exc}"
            )
            raise

        try:
            root = ET.fromstring(response.text)
        except ET.ParseError as exc:
            print(
                "SPOTWEB SERVICE: "
                f"Invalid XML response for book search "
                f"(query={query!r}, limit={limit}): {exc}"
            )
            raise

        return self._parse_results(root)

    def get_details(
        self,
        guid: str,
    ) -> SpotwebResult | None:

        settings = config_service.load()

        params = {
            "t": "details",
            "id": guid,
            "apikey": settings.spotweb.api_key,
        }

        try:
            response = requests.get(
                self._get_api_url(),
                params=params,
                timeout=30,
            )
            response.raise_for_status()

        except requests.RequestException as exc:
            print(
                "SPOTWEB SERVICE: "
                f"Details request failed "
                f"(guid={guid}): {exc}"
            )
            raise

        try:
            root = ET.fromstring(response.text)
        except ET.ParseError as exc:
            print(
                "SPOTWEB SERVICE: "
                f"Invalid XML response for details "
                f"(guid={guid}): {exc}"
            )
            raise

        results = self._parse_results(root)

        if not results:
            return None

        return results[0]

    def _parse_results(
        self,
        root: ET.Element,
    ) -> list[SpotwebResult]:

        results = []

        for item in root.findall("./channel/item"):

            guid = item.findtext("guid")
            title = item.findtext("title")
            link = item.findtext("link")
            pub_date = item.findtext("pubDate")
            description = item.findtext("description") or ""

            size = 0

            for attr in item.findall(
                "{http://www.newznab.com/DTD/2010/feeds/attributes/}attr"
            ):

                if attr.attrib.get("name") == "size":

                    try:
                        size = int(
                            attr.attrib.get("value", "0")
                        )
                    except ValueError:
                        size = 0

            categories = [
                attr.attrib.get("value")
                for attr in item.findall(
                    "{http://www.newznab.com/DTD/2010/feeds/attributes/}attr"
                )
                if attr.attrib.get("name") == "category"
            ]

            category = (
                categories[-1]
                if categories
                else ""
            )

            if not guid or not title or not pub_date:
                continue

            published_at = datetime.strptime(
                pub_date,
                "%a, %d %b %Y %H:%M:%S %z",
            )

            results.append(
                SpotwebResult(
                    guid=guid,
                    title=title,
                    download_url=link or "",
                    size=size,
                    published_at=published_at,
                    category=category,
                    description=description,
                )
            )

        return results


spotweb_service = SpotwebService()