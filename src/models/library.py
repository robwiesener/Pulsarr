from datetime import datetime

from sqlmodel import Field, SQLModel


class Library(SQLModel, table=True):

    __tablename__ = "library"

    id: int | None = Field(
        default=None,
        primary_key=True,
    )

    calibre_id: str = Field(
        unique=True,
        index=True,
    )

    title: str

    author: str

    series: str | None = None

    series_index: float | None = None

    description: str | None = None

    rating: float | None = None

    uploaded_at: datetime | None = None

    cover_url: str | None = None

    epub_url: str | None = None
    epub_size: int | None = None
    epub_mtime: datetime | None = None

    local_cover_path: str | None = None
    local_epub_path: str | None = None
