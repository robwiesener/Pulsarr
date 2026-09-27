"""
Pulsarr - Book Match Service

Contains matching logic for books against Spotweb results.
"""

import re
import unicodedata


def _normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = value.encode("ascii", "ignore").decode("ascii")
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def _author_variants(author: str) -> set[str]:
    normalized = _normalize(author)
    parts = normalized.split()

    if len(parts) < 2:
        return {normalized}

    return {
        normalized,
        " ".join(reversed(parts)),
    }


def _contains_title_and_author(
    text: str,
    title: str,
    author: str,
) -> bool:

    normalized_text = _normalize(text)
    normalized_title = _normalize(title)

    if not normalized_title:
        return False

    if normalized_title not in normalized_text:
        return False

    for author_variant in _author_variants(author):
        if author_variant in normalized_text:
            return True

    return False


def match_spot_title(
    book_title: str,
    book_author: str,
    spot_title: str,
) -> bool:

    return _contains_title_and_author(
        text=spot_title,
        title=book_title,
        author=book_author,
    )

def match_title_or_author(
    book_title: str,
    book_author: str,
    text: str,
) -> bool:
    normalized_text = _normalize(text)

    normalized_title = _normalize(book_title)
    if normalized_title and normalized_title in normalized_text:
        return True

    for author_variant in _author_variants(book_author):
        if author_variant and author_variant in normalized_text:
            return True

    return False

def match_package_description(
    book_title: str,
    book_author: str,
    description: str,
) -> bool:

    # Spotweb packages contain one book per line.
    # Check each line independently so that words from
    # unrelated books or prose cannot create a false match.

    lines = re.split(
        r"<br\s*/?>|\r?\n",
        description,
    )

    for line in lines:

        line = line.strip()

        if not line:
            continue

        if _contains_title_and_author(
            text=line,
            title=book_title,
            author=book_author,
        ):
            return True

    return False


def book_matches(
    book_title: str,
    book_author: str,
    spot_title: str,
    description: str,
) -> bool:

    if match_spot_title(
        book_title=book_title,
        book_author=book_author,
        spot_title=spot_title,
    ):
        return True

    return match_package_description(
        book_title=book_title,
        book_author=book_author,
        description=description,
    )