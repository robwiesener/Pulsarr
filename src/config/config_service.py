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
            return AppSettings()

        with open(CONFIG_FILE, "r") as f:
            data = json.load(f)

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


config_service = ConfigService()