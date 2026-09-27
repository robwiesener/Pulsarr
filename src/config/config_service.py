from pathlib import Path
import json
import os

from src.config.settings import AppSettings


CONFIG_DIR = Path(
    os.getenv("PULSARR_CONFIG_DIR", "config")
)

CONFIG_FILE = CONFIG_DIR / "config.json"


class ConfigService:

    def load(self) -> AppSettings:

        if not CONFIG_FILE.exists():
            data = {}
        else:
            with open(CONFIG_FILE, "r") as f:
                data = json.load(f)

        # Environment variables overschrijven config.json (indien gezet).
        # Zo kun je in Docker secrets via env vars injecteren zonder
        # de UI-functionaliteit te verliezen.
        spotweb_env = os.getenv("SPOTWEB_API_KEY")
        if spotweb_env:
            data.setdefault("spotweb", {})["api_key"] = spotweb_env

        sabnzbd_env = os.getenv("SABNZBD_API_KEY")
        if sabnzbd_env:
            data.setdefault("sabnzbd", {})["api_key"] = sabnzbd_env

        return AppSettings(**data)

    def save(self, settings: AppSettings):

        CONFIG_FILE.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with open(CONFIG_FILE, "w") as f:
            json.dump(
                settings.model_dump(),
                f,
                indent=4,
            )

        # Bestandsrechten beperken tot de eigenaar (Unix only).
        try:
            os.chmod(CONFIG_FILE, 0o600)
        except OSError:
            pass


config_service = ConfigService()