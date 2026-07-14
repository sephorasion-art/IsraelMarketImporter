from __future__ import annotations

import re
from typing import Any

from engine.dom_analyzer import DomAnalyzer
from engine.image_detector import ImageDetector
from engine.link_detector import LinkDetector
from engine.price_detector import PriceDetector


def _clean_text(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip()


class ProductDetector:
    """Convert DOM candidates into normalized product dictionaries."""

    def __init__(self) -> None:
        self.dom = DomAnalyzer()
        self.prices = PriceDetector()
        self.images = ImageDetector()
        self.links = LinkDetector()

    def detect_from_dom(self, html: str, base_url: str = "") -> list[dict[str, Any]]:
        soup = self.dom.soup(html)
        cards = self.dom.find_product_cards(soup)
        products: list[dict[str, Any]] = []

        for card in cards:
            title_node = (
                card.select_one("h1")
                or card.select_one("h2")
                or card.select_one("h3")
                or card.select_one(".title")
                or card.select_one(".product-title")
            )
            price_node = card.select_one(".price") or card.select_one(".product-price") or card.select_one(".amount")
            link_node = card.select_one("a[href]")

            title = _clean_text(title_node.get_text(" ", strip=True) if title_node else "")
            href = link_node.get("href", "") if link_node else ""
            url = self.links.normalize(href, base_url)
            description = _clean_text(card.get_text(" ", strip=True))
            price = self.prices.parse_price(price_node.get_text(" ", strip=True) if price_node else description)
            images = self.images.extract_from_node(card, base_url)

            if not title and not url:
                continue

            products.append(
                {
                    "title": title,
                    "description": description,
                    "price": price,
                    "currency": "",
                    "url": url,
                    "images": images,
                    "sku": "",
                }
            )

        return products
