from __future__ import annotations

import re


class SchemaDetector:
    """Detect schema.org microdata markers in HTML."""

    _PATTERN = re.compile(r"itemtype\s*=\s*['\"]https?://schema\.org/", re.IGNORECASE)

    def has_schema_microdata(self, html: str) -> bool:
        if not html:
            return False
        return bool(self._PATTERN.search(html))
