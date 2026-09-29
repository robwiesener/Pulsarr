from pathlib import Path
import os

from tempfile import NamedTemporaryFile

import requests
from PIL import Image

from src.config.config_service import config_service


class LibraryStorageService:

    # Maximale afmetingen voor thumbnails.
    # Covers worden bij download verkleind naar deze afmetingen.
    THUMBNAIL_MAX_WIDTH = 300
    THUMBNAIL_MAX_HEIGHT = 450
    THUMBNAIL_QUALITY = 85

    def __init__(self):
        settings = config_service.load()

        root_dir = Path(
            os.getenv(
                "PULSARR_LIBRARY_ROOT",
                settings.storage.root_dir,
            )
        )

        self.library_dir = (
            root_dir
            / settings.storage.library_dir
        )

        self.downloads_dir = (
            root_dir
            / settings.storage.downloads_dir
        )

        self.library_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.downloads_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

    def get_cover_path(
        self,
        calibre_book_id: int,
    ) -> Path:

        return (
            self.library_dir
            / f"{calibre_book_id}.jpg"
        )

    def _make_thumbnail(
        self,
        image_path: Path,
    ) -> None:

        # Verklein de afbeelding in-place naar thumbnail-formaat.
        with Image.open(image_path) as img:

            img.thumbnail(
                (
                    self.THUMBNAIL_MAX_WIDTH,
                    self.THUMBNAIL_MAX_HEIGHT,
                )
            )

            # JPEG ondersteunt geen alpha-kanaal.
            if img.mode in ("RGBA", "LA", "P"):
                img = img.convert("RGB")

            img.save(
                image_path,
                "JPEG",
                quality=self.THUMBNAIL_QUALITY,
                optimize=True,
            )

    def download_cover(
        self,
        calibre_book_id: int,
        url: str,
    ) -> Path | None:

        destination = self.get_cover_path(
            calibre_book_id
        )

        if destination.is_file():
            print(
                "LIBRARY STORAGE: cover already exists - "
                f"{destination}"
            )
            return destination

        temporary_path = None

        try:
            with requests.get(
                url,
                timeout=30,
            ) as response:

                response.raise_for_status()

                with NamedTemporaryFile(
                    mode="wb",
                    dir=self.library_dir,
                    prefix=".cover-",
                    suffix=".tmp",
                    delete=False,
                ) as temporary_file:

                    temporary_path = Path(
                        temporary_file.name
                    )

                    for chunk in response.iter_content(
                        chunk_size=1024 * 1024,
                    ):

                        if chunk:
                            temporary_file.write(chunk)

            # Verklein naar thumbnail voordat we het bestand
            # naar de definitieve locatie verplaatsen.
            try:
                self._make_thumbnail(temporary_path)

            except Exception as exc:
                # Als thumbnail-generatie faalt, gebruik dan de
                # originele afbeelding. Beter een grote cover dan
                # helemaal geen cover.
                print(
                    "LIBRARY STORAGE: thumbnail generation failed - "
                    f"{url}: {exc}"
                )

            temporary_path.replace(
                destination
            )

            print(
                "LIBRARY STORAGE: downloaded cover - "
                f"{destination}"
            )

            return destination

        except Exception as exc:

            print(
                "LIBRARY STORAGE: cover download failed - "
                f"{url}: {exc}"
            )

            if temporary_path is not None:
                temporary_path.unlink(
                    missing_ok=True
                )

            return None


library_storage_service = LibraryStorageService()