from pydantic import BaseModel, Field


class SpotwebSettings(BaseModel):
    url: str = ""
    api_key: str = ""


class SabnzbdSettings(BaseModel):
    url: str = ""
    api_key: str = ""
    category: str = "books"


class CalibreSettings(BaseModel):
    url: str = ""


class StorageSettings(BaseModel):
    library_dir: str = "Library"
    downloads_dir: str = "Downloads"
    root_dir: str = "."


class WishlistSettings(BaseModel):
    description_search_keywords: str = (
        "pakket, boekenpakket"
    )


class BackgroundSettings(BaseModel):

    download_status_interval: int = Field(
        default=30,
        ge=15,
    )

    wishlist_search_interval: int = Field(
        default=900,
        ge=300,
    )


class AppSettings(BaseModel):
    spotweb: SpotwebSettings = SpotwebSettings()
    sabnzbd: SabnzbdSettings = SabnzbdSettings()
    calibre: CalibreSettings = CalibreSettings()
    background: BackgroundSettings = BackgroundSettings()
    wishlist: WishlistSettings = WishlistSettings()
    storage: StorageSettings = StorageSettings()