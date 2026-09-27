from pathlib import Path
import sys


sys.path.append(
    str(Path(__file__).resolve().parents[1])
)


from src.services.spotweb_service import spotweb_service


print("Fetching Spotweb releases...\n")


results = spotweb_service.fetch_recent_books(
    limit=100
)


print(
    f"Found {len(results)} results\n"
)


for result in results[:10]:

    print("----------------------------------------")

    print(
        f"GUID        : {result.guid}"
    )

    print(
        f"Title       : {result.title}"
    )

    print(
        f"Published   : {result.published_at}"
    )

    print(
        f"Size        : "
        f"{result.size / 1024 / 1024:.1f} MB"
    )

    print(
        f"Category    : {result.category}"
    )

    print(
        f"Download URL: {result.download_url}"
    )