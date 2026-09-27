import sys
from pathlib import Path

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1])
)

from src.services.spotweb_service import spotweb_service

print("Fetching Spotweb releases...")

results = spotweb_service.fetch_recent_books_paginated(
    pages=3,
    page_size=100,
)

print()
print(f"Total results: {len(results)}")
print()

for result in results[:5]:
    print(
        f"{result.published_at} - "
        f"{result.title}"
    )