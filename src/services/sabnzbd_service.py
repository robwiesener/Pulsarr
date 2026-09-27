import requests

from src.config.config_service import config_service
from src.models.enums import DownloadStatus

class SabnzbdService:

    def test_connection(self) -> tuple[bool, str]:

        settings = config_service.load()

        url = (
            settings.sabnzbd.url.rstrip("/")
            + "/api"
        )

        params = {
            "mode": "version",
            "output": "json",
            "apikey": settings.sabnzbd.api_key,
        }

        try:
            response = requests.get(
                url,
                params=params,
                timeout=5,
            )

            response.raise_for_status()

            data = response.json()

            print("SABNZBD TEST RESPONSE:", data)

            if "version" in data: 
                return True, f"SABnzbd {data['version']} connection test successful."

            return False, "SABnzbd connection failed."

        except Exception as exc:
            return False, str(exc)

    def add_url(self, download_url: str) -> tuple[bool, str, str | None]:

        settings = config_service.load()

        url = (
            settings.sabnzbd.url.rstrip("/")
            + "/api"
        )

        params = {
            "mode": "addurl",
            "name": download_url,
            "cat": settings.sabnzbd.category,
            "output": "json",
            "apikey": settings.sabnzbd.api_key,
        }

        try:
            response = requests.get(
                url,
                params=params,
                timeout=10,
            )

            response.raise_for_status()

            data = response.json()

            print("SABNZBD ADDURL RESPONSE:", data)

            if data.get("status") is True:

                nzo_ids = data.get("nzo_ids", [])

                nzo_id = nzo_ids[0] if nzo_ids else None

                return (
                    True,
                    "Download added to SABnzbd.",
                    nzo_id,
                )

            return (
                False,
                data.get(
                    "error",
                    "SABnzbd rejected the download.",
                ),
                None,
            )

        except Exception as exc:

            print("SABNZBD ADDURL ERROR:", exc)

            return (
                False,
                str(exc),
                None,
            )

    def get_download_status(self, sabnzbd_id: str) -> tuple[bool, str, str | None]:

        settings = config_service.load()

        url = (
            settings.sabnzbd.url.rstrip("/")
            + "/api"
        )

        # Eerst de actieve queue controleren
        params = {
            "mode": "queue",
            "output": "json",
            "apikey": settings.sabnzbd.api_key,
        }

        try:
            response = requests.get(
                url,
                params=params,
                timeout=10,
            )

            response.raise_for_status()

            data = response.json()

            queue = data.get("queue", {})
            slots = queue.get("slots", [])

            for slot in slots:

                if slot.get("nzo_id") == sabnzbd_id:

                    status = slot.get(
                        "status",
                        "Downloading",
                    )

                    print(
                        f"SABnzbd queue match: "
                        f"{sabnzbd_id} -> {status}"
                    )

                    return True, DownloadStatus.DOWNLOADING, None

        except Exception as exc:

            print(
                "SABNZBD QUEUE STATUS ERROR:",
                exc,
            )

            return False, "ERROR", str(exc)

        # Niet gevonden in queue.
        # Nu de history controleren.
        params = {
            "mode": "history",
            "output": "json",
            "apikey": settings.sabnzbd.api_key,
            "limit": 100,
        }

        try:
            response = requests.get(
                url,
                params=params,
                timeout=10,
            )

            response.raise_for_status()

            data = response.json()

            history = data.get("history", {})
            slots = history.get("slots", [])

            for slot in slots:

                if slot.get("nzo_id") != sabnzbd_id:
                    continue

                status = slot.get("status", "")
                storage = slot.get("storage")

                print(
                    f"SABnzbd history match: "
                    f"{sabnzbd_id} -> {status}"
                )

                if status == "Extracting":
                    return True, DownloadStatus.DOWNLOADING, storage

                if status == "Completed":
                    return True, DownloadStatus.DOWNLOADED, storage

                if status in (
                    "Failed",
                    "Failed/Retry",
                ):

                    fail_message = slot.get(
                        "fail_message",
                        "",
                    )

                    return (
                        False,
                        DownloadStatus.DOWNLOAD_FAILED,
                        fail_message,
                    )

                return False, status or "UNKNOWN", None

            print(
                f"SABnzbd download {sabnzbd_id} "
                "not found in queue or history."
            )

            return False, "NOT_FOUND", None

        except Exception as exc:

            print(
                "SABNZBD HISTORY STATUS ERROR:",
                exc,
            )

            return False, "ERROR", str(exc)

    def get_download_history(self, nzo_id: str) -> tuple[bool, str]:

        settings = config_service.load()

        url = (
            settings.sabnzbd.url.rstrip("/")
            + "/api"
        )

        params = {
            "mode": "history",
            "output": "json",
            "apikey": settings.sabnzbd.api_key,
            "limit": 100,
        }

        try:
            response = requests.get(
                url,
                params=params,
                timeout=10,
            )

            response.raise_for_status()

            data = response.json()

            print("SABNZBD HISTORY RESPONSE:", data)

            slots = data.get("history", {}).get("slots", [])

            for slot in slots:

                if slot.get("nzo_id") == nzo_id:

                    status = slot.get("status", "")
                    return True, status

            return False, "Download not found in SABnzbd history."

        except Exception as exc:

            print("SABNZBD HISTORY ERROR:", exc)

            return False, str(exc)

sabnzbd_service = SabnzbdService()
