from typing import Optional

from sqlmodel import SQLModel, Field

from src.models.enums import SearchType, DownloadStatus


class SearchResultRecord(SQLModel, table=True):

    __tablename__ = "search_results"

    id: Optional[int] = Field(
        default=None,
        primary_key=True,
    )

    book_id: int | None = Field(
        default=None,
        index=True,
    )

    search_title: str | None = Field(
        default=None,
    )

    search_author: str | None = Field(
        default=None,
    )

    guid: str = Field(
        index=True,
    )

    description: str

    download_url: str

    size: int

    age: int

    category: str

    search_type: SearchType = Field(
        default=SearchType.BOOK,
    )

    download_status: DownloadStatus = Field(
        default=DownloadStatus.POSSIBLE_MATCH,
    )

    sabnzbd_id: str | None = Field(
        default=None,
        index=True,
    )