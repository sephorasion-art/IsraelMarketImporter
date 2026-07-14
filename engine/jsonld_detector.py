from __future__ import annotations

import re


class JsonLdDetector:
    """Detect JSON-LD scripts in HTML."""

    _PATTERN = re.compile(r"application/ld\+json", re.IGNORECASE)

    def has_jsonld(self, html: str) -> bool:
        if not html:
            return False
        return bool(self._PATTERN.search(html))
