from dataclasses import dataclass

@dataclass
class SearchResult:
    guid: str
    description: str
    download_url: str
    size: int
    age: int
    category: str