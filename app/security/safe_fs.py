"""Pulsarr - Safe filesystem helpers.

Voorkomt path traversal en weigert symlinks. Gebruikt door
library_routes en library_storage_service.
"""

from pathlib import Path


def is_under(path: Path, base: Path) -> bool:
    """True als path (na resolve) onder base valt."""
    try:
        Path(path).resolve().relative_to(Path(base).resolve())
        return True
    except ValueError:
        return False


def safe_path_within(path: Path, base: Path) -> Path:
    """Resolve path en verifieer dat die onder base valt.

    Weigert symlinks. Geeft het geresolveerde pad terug.

    Raises:
        ValueError: als path buiten base valt of een symlink is.
    """
    p = Path(path)

    if p.is_symlink():
        raise ValueError(f"Symlink not allowed: {p}")

    resolved = p.resolve()
    base_resolved = Path(base).resolve()

    try:
        resolved.relative_to(base_resolved)
    except ValueError:
        raise ValueError(
            f"Path {resolved} is outside {base_resolved}"
        )

    return resolved
