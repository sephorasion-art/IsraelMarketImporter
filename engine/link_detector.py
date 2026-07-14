from __future__ import annotations

import re
from urllib.parse import urljoin


class LinkDetector:
    """Detect product-like links in catalog pages."""

    _PRODUCT_PATTERN = re.compile(r"product|products|productinfo|item|sku|/p/|/dp/", re.IGNORECASE)

    def normalize(self, href: str, base_url: str = "") -> str:
        if not href:
            return ""
        if href.startswith("//"):
            return "https:" + href
        if href.startswith("/") and base_url:
            return urljoin(base_url, href)
        return href

    def is_product_link(self, href: str) -> bool:
        if not href or href.startswith("#") or href.lower().startswith("javascript:"):
            return False
        return bool(self._PRODUCT_PATTERN.search(href))
