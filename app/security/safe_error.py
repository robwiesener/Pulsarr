"""Pulsarr - Exception sanitization.

Verwijdert API keys en volledige URL's uit exception-strings
voordat ze naar de UI of activity log gaan.

Requests-exceptions bevatten de URL in twee vormen:
- Volledig:  https://host/path?apikey=...  (zeldzaam)
- Relatief:  url: /api?mode=...&apikey=...  (meestal)

Beide moeten worden afgedekt.
"""

import re


def sanitize_exception(exc: Exception) -> str:
    text = str(exc)

    # 1. Redigeer apikey-waarden, ongeacht URL-context
    text = re.sub(
        r"(?i)(apikey=)[^\s&'\"\)\]]+",
        r"\1<redacted>",
        text,
    )

    # 2. Strip volledige URL's (met scheme)
    text = re.sub(r"https?://\S+", "<url>", text)

    return text
