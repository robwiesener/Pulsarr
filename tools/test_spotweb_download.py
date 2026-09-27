import sys
from pathlib import Path

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1])
)


from sqlmodel import Session

from src.db.database import engine
from src.models.search_result_record import SearchResultRecord
from src.services.sabnzbd_service import sabnzbd_service


RECORD_ID = 4


with Session(engine) as session:

    record = session.get(
        SearchResultRecord,
        RECORD_ID,
    )

    if not record:
        print(f"Record {RECORD_ID} not found")
        raise SystemExit(1)

    print("Record:")
    print("  ID          :", record.id)
    print("  Title       :", record.search_title)
    print("  Author      :", record.search_author)
    print("  GUID        :", record.guid)
    print("  Download URL:", record.download_url)
    print()

    print("Sending URL to SABnzbd...")

    success, message, nzo_id = sabnzbd_service.add_url(
        record.download_url
    )

    print()
    print("Result:")
    print("  Success :", success)
    print("  Message :", message)
    print("  NZO ID  :", nzo_id)