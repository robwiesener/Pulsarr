"""
Pulsarr - Enumerations

This module contains shared enumerations used throughout the application.

Currently available:
- Status
- Search Type
- Download Status

Enums provide a single source of truth for values that are
used in both the backend and the user interface.
"""

from enum import Enum


class Status(str, Enum):
    UNAVAILABLE = "Unavailable"
    POSSIBLE_MATCH = "Possible Match"
    DOWNLOADING = "Downloading"
    DOWNLOAD_FAILED = "Download Failed"
    DOWNLOADED = "Downloaded"

    @property
    def badge_class(self) -> str:
        return {
            Status.UNAVAILABLE: "status-unavailable",
            Status.POSSIBLE_MATCH: "status-found",
            Status.DOWNLOADING: "status-downloading",
            Status.DOWNLOAD_FAILED: "status-failed",
            Status.DOWNLOADED: "status-downloaded",
        }[self]


class SearchType(str, Enum):
    BOOK = "BOOK"
    TITLE = "TITLE"
    AUTHOR = "AUTHOR"


class DownloadStatus(str, Enum):
    POSSIBLE_MATCH = "Possible Match"
    DOWNLOADING = "Downloading"
    DOWNLOAD_FAILED = "Download Failed"
    DOWNLOADED = "Downloaded"

    @property
    def badge_class(self) -> str:
        return {
            DownloadStatus.POSSIBLE_MATCH: "status-found",
            DownloadStatus.DOWNLOADING: "status-downloading",
            DownloadStatus.DOWNLOAD_FAILED: "status-failed",
            DownloadStatus.DOWNLOADED: "status-downloaded",
        }[self]