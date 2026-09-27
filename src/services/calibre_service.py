import html
import re
from datetime import datetime
from urllib.parse import urljoin
from xml.etree import ElementTree as ET

import requests

from src.config.config_service import config_service


class CalibreService:

    ATOM_NAMESPACE = "http://www.w3.org/2005/Atom"

    def get_base_url(self) -> str:
        settings = config_service.load()
        return settings.calibre.url.rstrip("/")

    def get_opds_url(self) -> str:
        return (
            f"{self.get_base_url()}"
            "/opds?library_id=04.Calibre"
        )

    def get_books(self) -> list[dict]:
        response = requests.get(
            self.get_opds_url(),
            timeout=10,
        )
        response.raise_for_status()

        root = ET.fromstring(response.content)

        namespace = {
            "atom": self.ATOM_NAMESPACE,
        }

        newest_url = None

        for entry in root.findall(
            "atom:entry",
            namespace,
        ):
            title = entry.findtext(
                "atom:title",
                default="",
                namespaces=namespace,
            )

            if title == "By Newest":
                link = entry.find(
                    "atom:link",
                    namespace,
                )

                if link is not None:
                    newest_url = link.attrib.get("href")

                break

        if not newest_url:
            raise RuntimeError(
                "Could not find 'By Newest' feed in Calibre OPDS"
            )

        newest_url = urljoin(
            self.get_base_url() + "/",
            html.unescape(newest_url),
        )

        return self._get_books_from_feed(newest_url)

    def _get_books_from_feed(
        self,
        url: str,
    ) -> list[dict]:
        books = []

        namespace = {
            "atom": self.ATOM_NAMESPACE,
        }

        while url:
            response = requests.get(
                url,
                timeout=10,
            )
            response.raise_for_status()

            root = ET.fromstring(response.content)

            for entry in root.findall(
                "atom:entry",
                namespace,
            ):
                title = entry.findtext(
                    "atom:title",
                    default="",
                    namespaces=namespace,
                )

                author = entry.findtext(
                    "atom:author/atom:name",
                    default="",
                    namespaces=namespace,
                )

                calibre_id = entry.findtext(
                    "atom:id",
                    default="",
                    namespaces=namespace,
                )

                content = entry.find(
                    "atom:content",
                    namespace,
                )

                description = None
                rating = None
                series = None
                series_index = None

                if content is not None:
                    raw_content = "".join(
                        content.itertext()
                    )

                    description = self._parse_content(
                        raw_content
                    )

                    rating = self._extract_rating(
                        content
                    )

                    series, series_index = (
                        self._extract_series(content)
                    )

                published = entry.findtext(
                    "atom:published",
                    default="",
                    namespaces=namespace,
                )

                uploaded_at = self._parse_datetime(
                    published
                )

                cover_url = None
                epub_url = None
                epub_size = None
                epub_mtime = None

                for link in entry.findall(
                    "atom:link",
                    namespace,
                ):
                    rel = link.attrib.get("rel")
                    href = link.attrib.get("href")

                    if not href:
                        continue

                    href = urljoin(
                        self.get_base_url() + "/",
                        html.unescape(href),
                    )

                    if rel == "http://opds-spec.org/cover":
                        cover_url = href

                    elif (
                        rel
                        == "http://opds-spec.org/acquisition"
                        and link.attrib.get("type")
                        == "application/epub+zip"
                    ):
                        epub_url = href

                        length = link.attrib.get(
                            "length"
                        )

                        if length:
                            try:
                                epub_size = int(length)
                            except ValueError:
                                epub_size = None

                        mtime = link.attrib.get(
                            "mtime"
                        )

                        if mtime:
                            epub_mtime = (
                                self._parse_datetime(mtime)
                            )

                books.append(
                    {
                        "calibre_id": calibre_id,
                        "title": title,
                        "author": author,
                        "series": series,
                        "series_index": series_index,
                        "description": description,
                        "rating": rating,
                        "uploaded_at": uploaded_at,
                        "cover_url": cover_url,
                        "epub_url": epub_url,
                        "epub_size": epub_size,
                        "epub_mtime": epub_mtime,
                    }
                )

            next_url = None

            for link in root.findall(
                "atom:link",
                namespace,
            ):
                if link.attrib.get("rel") == "next":
                    next_url = link.attrib.get("href")
                    break

            if next_url:
                url = urljoin(
                    self.get_base_url() + "/",
                    html.unescape(next_url),
                )
            else:
                url = None

        return books

    def _parse_content(
        self,
        content: str,
    ) -> str | None:
        content = html.unescape(content)

        # Remove Calibre rating metadata.
        # Example:
        # RATING: ★★★★★
        content = re.sub(
            r"^\s*RATING:\s*★+\s*",
            "",
            content,
            count=1,
            flags=re.IGNORECASE,
        )

        # Remove Calibre tags metadata.
        # Only remove the TAGS line at the beginning.
        content = re.sub(
            r"^\s*TAGS:\s*[^\r\n]*(?:\r?\n|$)",
            "",
            content,
            count=1,
            flags=re.IGNORECASE,
        )

        # Remove Calibre series metadata.
        # Example:
        # SERIES: Vera Bergström [3]
        content = re.sub(
            r"^\s*SERIES:\s*[^\r\n]*(?:\r?\n|$)",
            "",
            content,
            count=1,
            flags=re.IGNORECASE,
        )

        # Remove remaining HTML tags.
        content = re.sub(
            r"<[^>]+>",
            " ",
            content,
        )

        # Normalize whitespace.
        content = re.sub(
            r"\s+",
            " ",
            content,
        ).strip()

        return content or None

    def _extract_rating(
        self,
        content,
    ) -> float | None:
        if content is None:
            return None

        text = "".join(
            content.itertext()
        )

        match = re.search(
            r"RATING:\s*(★+)",
            text,
            flags=re.IGNORECASE,
        )

        if not match:
            return None

        return float(
            len(match.group(1))
        )

    def _extract_series(
        self,
        content,
    ) -> tuple[str | None, float | None]:
        if content is None:
            return None, None

        text = "".join(
            content.itertext()
        )

        match = re.search(
            r"SERIES:\s*(.*?)\s*\[(.*?)\]",
            text,
            flags=re.IGNORECASE,
        )

        if not match:
            return None, None

        series = match.group(1).strip()

        try:
            series_index = float(
                match.group(2).strip()
            )
        except ValueError:
            series_index = None

        return series, series_index

    def _parse_datetime(
        self,
        value: str,
    ) -> datetime | None:
        if not value:
            return None

        try:
            return datetime.fromisoformat(
                value.replace(
                    "Z",
                    "+00:00",
                )
            )
        except ValueError:
            return None


calibre_service = CalibreService()