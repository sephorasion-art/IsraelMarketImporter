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


def _first_text(card, selectors: tuple[str, ...]) -> str:
    for selector in selectors:
        node = card.select_one(selector)
        if not node:
            continue
        text = _clean_text(node.get_text(" ", strip=True))
        if text:
            return text
        for attr in ("content", "value", "data-value"):
            raw = node.get(attr)
            if isinstance(raw, str):
                text = _clean_text(raw)
                if text:
                    return text
    return ""


def detect_title(card) -> str:
    return _first_text(
        card,
        (
            "h1",
            "h2",
            "h3",
            ".title",
            ".product-title",
            "[itemprop='name']",
            "[data-testid*='title' i]",
        ),
    )


def detect_description(card, page_soup=None) -> str:
    description = _first_text(
        card,
        (
            ".description",
            ".product-description",
            "[itemprop='description']",
            "p",
        ),
    )
    return description or _clean_text(card.get_text(" ", strip=True))


def detect_price(card, price_detector: PriceDetector) -> float | None:
    price_text = _first_text(
        card,
        (
            ".price",
            ".product-price",
            ".amount",
            "[itemprop='price']",
            "[data-price]",
        ),
    )
    return price_detector.parse_price(price_text) or price_detector.detect_in_text(card.get_text(" ", strip=True))


def detect_compare_price(card, price_detector: PriceDetector) -> float | None:
    compare_text = _first_text(
        card,
        (
            ".compare-at-price",
            ".old-price",
            ".was-price",
            ".original-price",
            "[data-compare-price]",
        ),
    )
    return price_detector.parse_price(compare_text)


def detect_gallery(card, image_detector: ImageDetector, base_url: str = "") -> list[str]:
    return image_detector.extract_from_node(card, base_url)


def detect_image(card, image_detector: ImageDetector, base_url: str = "") -> str:
    gallery = detect_gallery(card, image_detector, base_url=base_url)
    return gallery[0] if gallery else ""


def detect_brand(card) -> str:
    brand = _first_text(
        card,
        (
            "[itemprop='brand']",
            ".brand",
            ".product-brand",
            "[data-brand]",
        ),
    )
    if brand:
        return brand
    match = re.search(r"\bbrand\s*[:#-]?\s*([A-Za-z0-9 .&'_-]{2,})", card.get_text(" ", strip=True), re.I)
    return _clean_text(match.group(1)) if match else ""


def detect_weight(card) -> float | None:
    text = _first_text(
        card,
        (
            ".weight",
            ".product-weight",
            "[itemprop='weight']",
            "[data-weight]",
        ),
    ) or card.get_text(" ", strip=True)
    match = re.search(r"(\d+(?:[.,]\d+)?)\s*(kg|g|mg|lb|oz|l|ml)\b", text, re.I)
    if not match:
        return None
    try:
        return float(match.group(1).replace(",", "."))
    except ValueError:
        return None


def detect_category(card) -> str:
    return _first_text(
        card,
        (
            "[itemprop='category']",
            ".category",
            ".product-category",
            "[data-category]",
        ),
    )


def detect_url(card, link_detector: LinkDetector, base_url: str = "") -> str:
    link = card.select_one("a[href]")
    href = link.get("href", "") if link else ""
    return link_detector.normalize(href, base_url)


def detect_sku(card) -> str:
    sku = _first_text(
        card,
        (
            "[itemprop='sku']",
            ".sku",
            ".product-sku",
            "[data-sku]",
        ),
    )
    if sku:
        return sku
    match = re.search(r"\b(?:sku|ref|reference|item\s*id)\s*[:#-]?\s*([A-Za-z0-9._-]{3,})\b", card.get_text(" ", strip=True), re.I)
    return _clean_text(match.group(1)) if match else ""


def detect_barcode(card) -> str:
    barcode = _first_text(
        card,
        (
            "[itemprop='gtin13']",
            "[itemprop='gtin12']",
            "[itemprop='gtin']",
            "[itemprop='barcode']",
            ".barcode",
            "[data-barcode]",
        ),
    )
    if barcode:
        return barcode
    match = re.search(r"\b(?:ean|gtin|barcode)\s*[:#-]?\s*(\d{8,14})\b", card.get_text(" ", strip=True), re.I)
    return _clean_text(match.group(1)) if match else ""


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
