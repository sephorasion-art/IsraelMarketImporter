from __future__ import annotations

import re


class GraphqlDetector:
    """Detect GraphQL usage from HTML or endpoint URLs."""

    _HTML_PATTERN = re.compile(r"graphql|apollo|__typename", re.IGNORECASE)

    def has_graphql(self, html: str, network_calls: list[str] | None = None) -> bool:
        if html and self._HTML_PATTERN.search(html):
            return True
        for call in network_calls or []:
            if "graphql" in (call or "").lower():
                return True
        return False
