from dataclasses import dataclass
from datetime import datetime


@dataclass
class SpotwebResult:
    guid: str
    title: str
    download_url: str
    size: int
    published_at: datetime
    category: str
    description: str = ""