import json
import re
from typing import Any, Iterable
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from engine.image_detector import ImageDetector
from engine.link_detector import LinkDetector
from engine.models import Product
from engine.price_detector import PriceDetector
from engine.product_detector import ProductDetector


_price_detector = PriceDetector()
_image_detector = ImageDetector()
_link_detector = LinkDetector()
_product_detector = ProductDetector()


def _clean_text(value: str | None) -> str:
    if not value:
        return ""
    text = re.sub(r"\s+", " ", value)
    return text.strip()


def _parse_price(value: str | None) -> float | None:
    return _price_detector.parse_price(value)


def _normalize_url(url: str, base_url: str = "") -> str:
    return _link_detector.normalize(url, base_url)


def _extract_jsonld_data(html: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "lxml")
    products = []

    for script in soup.find_all("script", type=lambda t: t and "application/ld+json" in t):
        try:
            payload = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue

        if isinstance(payload, list):
            candidates = payload
        elif isinstance(payload, dict) and payload.get("@graph"):
            candidates = payload["@graph"]
        else:
            candidates = [payload]

        for item in candidates:
            item_type = item.get("@type")
            if isinstance(item_type, list):
                item_type = item_type[0]

            if isinstance(item_type, str) and item_type.lower() == "product":
                product = {
                    "title": _clean_text(item.get("name") or item.get("headline") or ""),
                    "description": _clean_text(item.get("description") or ""),
                    "url": item.get("url") or "",
                    "sku": _clean_text(item.get("sku") or ""),
                    "price": _parse_price(item.get("offers", {}).get("price") if isinstance(item.get("offers"), dict) else item.get("price")),
                    "currency": item.get("offers", {}).get("priceCurrency") if isinstance(item.get("offers"), dict) else item.get("priceCurrency"),
                    "images": item.get("image") if isinstance(item.get("image"), list) else ([item.get("image")] if item.get("image") else []),
                }
                products.append(product)

    return products


def _extract_application_json_data(html: str) -> list[dict[str, Any]]:
    """Parse <script type="application/json"> blocks that may contain product data.

    This handles API JSON embeds where the script contains either a single product
    object or a list of products. We look for common product keys and normalize
    them into the same product shape as JSON-LD parsing.
    """
    soup = BeautifulSoup(html, "lxml")
    products = []

    for script in soup.find_all("script", type=lambda t: t and "application/json" in t):
        try:
            payload = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue

        candidates = []
        if isinstance(payload, list):
            candidates = payload
        elif isinstance(payload, dict):
            # If payload wraps data under a key like "products" or "items"
            if any(k in payload for k in ("products", "items", "data")):
                for k in ("products", "items", "data"):
                    if isinstance(payload.get(k), list):
                        candidates = payload.get(k)
                        break
            else:
                candidates = [payload]

        for item in candidates:
            if not isinstance(item, dict):
                continue

            # heuristic: consider this a product if it has name/title or offers/price
            if not (item.get("name") or item.get("title") or item.get("offers") or item.get("price")):
                continue

            price = None
            currency = ""
            offers = item.get("offers")
            if isinstance(offers, dict):
                price = _parse_price(offers.get("price") if offers.get("price") is not None else offers.get("priceCurrency"))
                currency = offers.get("priceCurrency") or ""
            else:
                price = _parse_price(item.get("price"))

            images = item.get("image") if isinstance(item.get("image"), list) else ([item.get("image")] if item.get("image") else [])

            product = {
                "title": _clean_text(item.get("name") or item.get("title") or ""),
                "description": _clean_text(item.get("description") or ""),
                "url": item.get("url") or "",
                "sku": _clean_text(item.get("sku") or ""),
                "price": price,
                "currency": currency,
                "images": images,
            }
            products.append(product)

    return products


def _extract_dom_products(soup: BeautifulSoup, base_url: str = "") -> list[dict[str, Any]]:
    return _product_detector.detect_from_dom(str(soup), base_url)


def _extract_link_based_products(soup: BeautifulSoup, base_url: str = "") -> list[dict[str, Any]]:
    """Generic fallback for catalog pages built mainly from product links.

    This is intentionally heuristic (not provider-specific): it looks for links
    that resemble product detail URLs and extracts title/price/image from nearby
    DOM context.
    """
    products: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    product_url_pattern = re.compile(r"product|products|productinfo|item|sku|/p/|/dp/", re.I)

    for link in soup.select("a[href]"):
        href = (link.get("href") or "").strip()
        if not _link_detector.is_product_link(href) or not product_url_pattern.search(href):
            continue

        title = _clean_text(link.get_text(" ", strip=True))
        if len(title) < 2:
            continue

        url = _link_detector.normalize(href, base_url)
        if not url or url in seen_urls:
            continue

        container = link.parent
        text_scope = _clean_text(container.get_text(" ", strip=True) if container else title)
        price = _price_detector.detect_in_text(text_scope)

        img_tag = None
        if container:
            img_tag = container.select_one("img")
        if not img_tag:
            img_tag = link.select_one("img")
        image = ""
        if img_tag:
            image = _image_detector.normalize(img_tag.get("src") or "", base_url)

        product = {
            "title": title,
            "price": price,
            "currency": "",
            "url": url,
            "description": text_scope,
            "images": [image] if image else [],
            "sku": "",
        }
        products.append(product)
        seen_urls.add(url)

    return products


def _extract_schema_microdata_products(soup: BeautifulSoup, base_url: str = "") -> list[dict[str, Any]]:
    products = []
    cards = soup.select("[itemtype*='schema.org/Product']")
    for card in cards:
        title_tag = card.select_one("[itemprop='name']")
        desc_tag = card.select_one("[itemprop='description']")
        price_tag = card.select_one("[itemprop='price']")
        sku_tag = card.select_one("[itemprop='sku']")
        brand_tag = card.select_one("[itemprop='brand']")
        image_tag = card.select_one("[itemprop='image'], img")
        link_tag = card.select_one("a[href]")

        image = ""
        if image_tag:
            image = image_tag.get("content") or image_tag.get("src") or ""

        product = {
            "title": _clean_text(title_tag.get_text(" ", strip=True) if title_tag else ""),
            "description": _clean_text(desc_tag.get_text(" ", strip=True) if desc_tag else ""),
            "url": _link_detector.normalize(link_tag.get("href", ""), base_url) if link_tag else "",
            "sku": _clean_text(sku_tag.get_text(" ", strip=True) if sku_tag else ""),
            "price": _parse_price((price_tag.get("content") if price_tag else "") or (price_tag.get_text(" ", strip=True) if price_tag else "")),
            "currency": "",
            "images": [_image_detector.normalize(image, base_url)] if image else [],
            "brand": _clean_text(brand_tag.get_text(" ", strip=True) if brand_tag else ""),
        }
        if product["title"] or product["url"]:
            products.append(product)
    return products


def _iter_dict_nodes(payload: Any) -> Iterable[dict[str, Any]]:
    if isinstance(payload, dict):
        yield payload
        for value in payload.values():
            yield from _iter_dict_nodes(value)
    elif isinstance(payload, list):
        for item in payload:
            yield from _iter_dict_nodes(item)


def _extract_images_from_item(item: dict[str, Any]) -> list[str]:
    images = item.get("images") or item.get("image") or item.get("media") or []
    if isinstance(images, str):
        return [images]
    if isinstance(images, dict):
        # Common shape: {"url": "..."}
        if isinstance(images.get("url"), str):
            return [images["url"]]
        return []
    if isinstance(images, list):
        out: list[str] = []
        for img in images:
            if isinstance(img, str):
                out.append(img)
            elif isinstance(img, dict) and isinstance(img.get("url"), str):
                out.append(img["url"])
        return out
    return []


def _extract_price_from_item(item: dict[str, Any]) -> float | None:
    direct = _price_detector.parse_price(str(item.get("price") or ""))
    if direct is not None:
        return direct
    for key in ("currentPrice", "salePrice", "unit_price", "final_price"):
        p = _price_detector.parse_price(str(item.get(key) or ""))
        if p is not None:
            return p
    for obj_key in ("pricing", "priceInfo", "price_data"):
        obj = item.get(obj_key)
        if isinstance(obj, dict):
            for k in ("price", "current", "amount", "value"):
                p = _price_detector.parse_price(str(obj.get(k) or ""))
                if p is not None:
                    return p
    return None


def _is_product_like(item: dict[str, Any]) -> bool:
    title = _clean_text(item.get("name") or item.get("title") or item.get("displayName") or "")
    sku_like = _clean_text(item.get("sku") or item.get("id") or item.get("productId") or "")
    has_price = _extract_price_from_item(item) is not None
    has_image = bool(_extract_images_from_item(item))
    return bool(title and (has_price or has_image or sku_like))


class UniversalParser:

    def parse(self, html: str, base_url: str = "") -> list[dict[str, Any]]:
        if not html:
            return []

        # Prefer explicit application/json embeds (API data) when available
        appjson_products = _extract_application_json_data(html)
        if appjson_products:
            return appjson_products

        jsonld_products = _extract_jsonld_data(html)
        if jsonld_products:
            return jsonld_products

        soup = BeautifulSoup(html, "lxml")
        schema_products = _extract_schema_microdata_products(soup, base_url)
        if schema_products:
            return schema_products
        products = _extract_dom_products(soup, base_url)
        if products:
            return products

        # Last-resort generic extraction for link-heavy catalogs.
        products = _extract_link_based_products(soup, base_url)
        return products

    def parse_products(self, html: str, base_url: str = "") -> list[Product]:
        items = self.parse(html, base_url)
        products: list[Product] = []
        for item in items:
            images = item.get("images") or []
            image = images[0] if images else ""
            products.append(
                Product(
                    title=item.get("title") or "",
                    description=item.get("description") or "",
                    price=item.get("price"),
                    compare_at_price=item.get("compare_at_price"),
                    sku=item.get("sku") or "",
                    barcode=item.get("barcode") or "",
                    brand=item.get("brand") or "",
                    category=item.get("category") or "",
                    image=image,
                    gallery=images,
                    stock=item.get("stock"),
                    weight=item.get("weight"),
                    tags=item.get("tags") or [],
                    url=item.get("url") or "",
                )
            )
        return products

    def parse_api_payloads(self, payloads: list[Any]) -> list[Product]:
        products: list[Product] = []
        seen: set[tuple[str, str]] = set()
        for payload in payloads or []:
            for item in _iter_dict_nodes(payload):
                if not _is_product_like(item):
                    continue
                title = _clean_text(item.get("name") or item.get("title") or item.get("displayName") or "")
                images = _extract_images_from_item(item)
                url = item.get("url") or item.get("productUrl") or ""
                sku = _clean_text(item.get("sku") or item.get("productId") or item.get("id") or "")

                dedupe_key = (title.lower(), sku or url)
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)

                products.append(
                    Product(
                        title=title,
                        description=_clean_text(item.get("description") or item.get("subtitle") or ""),
                        price=_extract_price_from_item(item),
                        compare_at_price=_parse_price(str(item.get("compare_at_price") or item.get("oldPrice") or "")),
                        sku=sku,
                        barcode=_clean_text(item.get("barcode") or ""),
                        brand=_clean_text(item.get("brand") or item.get("manufacturer") or ""),
                        category=_clean_text(item.get("category") or item.get("categoryName") or ""),
                        image=images[0] if images else "",
                        gallery=images,
                        stock=item.get("stock") if isinstance(item.get("stock"), int) else None,
                        tags=item.get("tags") if isinstance(item.get("tags"), list) else [],
                        url=url,
                    )
                )
        return products
