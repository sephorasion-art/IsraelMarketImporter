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
        "[data-testid*='product' i]",
        "[class*='product' i]",
        "[class*='item' i]",
        "article",
        ".card",
    ]

    def soup(self, html: str) -> BeautifulSoup:
        return BeautifulSoup(html or "", "lxml")

    def find_product_cards(self, soup: BeautifulSoup):
        best_cards = []
        best_count = 0

        for selector in self._SELECTORS:
            cards = soup.select(selector)
            count = len(cards)
            if count <= 0:
                continue

            # Avoid huge noisy selector matches (layout wrappers).
            if count > 3000:
                continue

            if count > best_count:
                best_cards = cards
                best_count = count

        return best_cards
