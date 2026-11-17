import re
from datetime import datetime

import xml.etree.ElementTree as ET

import requests

from sqlmodel import Session

from app.config.config_service import config_service
from app.db.database import engine
from app.models.spotweb_result import SpotwebResult
from app.security.safe_error import sanitize_exception
from app.services.activity_log_service import activity_log_service


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

    def _parse_xml_response(
        self,
        response: requests.Response,
        context: str,
    ) -> ET.Element:
        """Parse XML, met duidelijke fout bij HTML-respons (bv. loginpagina)."""
        content_type = response.headers.get("Content-Type", "").lower()
        body_start = response.text.lstrip()[:200].lower()

        if (
            "html" in content_type
            or body_start.startswith("<!doctype html")
            or body_start.startswith("<html")
        ):
            raise ValueError(
                f"Spotweb returned HTML instead of XML ({context}). "
                "Check Spotweb URL and API key under Configuration."
            )

        try:
            return ET.fromstring(response.text)
        except ET.ParseError as exc:
            raise ValueError(
                f"Invalid XML response ({context}): {exc}"
            )

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

            root = self._parse_xml_response(response, "test connection")

            if root.find("./channel") is not None:
                return True, "Spotweb connection test successful."

            return False, "Spotweb connection failed."

        except Exception as exc:
            return False, sanitize_exception(exc)

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
            safe = sanitize_exception(exc)
            print(f"SPOTWEB SERVICE: {message}: {safe}")
            self._log(
                level="ERROR",
                message=message,
                details=safe,
            )
            raise

        try:
            root = self._parse_xml_response(
                response,
                f"recent books offset={offset} limit={limit}",
            )
        except ValueError as exc:
            message = str(exc)
            print(f"SPOTWEB SERVICE: {message}")
            self._log(level="ERROR", message=message)
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
            safe = sanitize_exception(exc)
            print(
                "SPOTWEB SERVICE: "
                f"Book search request failed "
                f"(query={query!r}, limit={limit}): {safe}"
            )
            raise

        try:
            root = self._parse_xml_response(
                response,
                f"search query={query!r} limit={limit}",
            )
        except ValueError as exc:
            print(f"SPOTWEB SERVICE: {exc}")
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
            safe = sanitize_exception(exc)
            print(
                "SPOTWEB SERVICE: "
                f"Details request failed "
                f"(guid={guid}): {safe}"
            )
            raise

        try:
            root = self._parse_xml_response(
                response,
                f"details guid={guid}",
            )
        except ValueError as exc:
            print(f"SPOTWEB SERVICE: {exc}")
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
