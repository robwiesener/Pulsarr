from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.services.prowlarr_service import prowlarr_service


print("Searching Prowlarr...\n")

query = "Peter Varg"

results = prowlarr_service.search_books(query)

print(f"Query: {query}")
print(f"Found: {len(results)} results\n")


def format_size(size: int) -> str:
    return f"{size / 1024 / 1024:.1f} MB"


for result in results[:5]:

    print("----------------------------------------")
    print(f"GUID        : {result.guid}")
    print(f"Description : {result.description}")
    print(f"Size        : {format_size(result.size)}")
    print(f"Age         : {result.age} days")
    print(f"Category    : {result.category}")
    print(f"Download URL: {result.download_url}")