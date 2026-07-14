from __future__ import annotations

from bs4 import BeautifulSoup


class DomAnalyzer:
    """Locate candidate product cards in page DOM."""

    _SELECTORS = [
        ".product",
        ".product-card",
        ".product-item",
        ".product-listing",
        ".product-grid-item",
        "article",
        ".card",
    ]

    def soup(self, html: str) -> BeautifulSoup:
        return BeautifulSoup(html or "", "lxml")

    def find_product_cards(self, soup: BeautifulSoup):
        for selector in self._SELECTORS:
            cards = soup.select(selector)
            if cards:
                return cards
        return []
