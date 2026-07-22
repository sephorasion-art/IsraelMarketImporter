import json
import re
from typing import Any, Iterable
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from engine.image_detector import ImageDetector
from engine.link_detector import LinkDetector
from engine.models import Product
from engine.price_detector import PriceDetector
from engine.product_detector import (
    ProductDetector,
    detect_barcode as dom_detect_barcode,
    detect_brand as dom_detect_brand,
    detect_category as dom_detect_category,
    detect_compare_price as dom_detect_compare_price,
    detect_description as dom_detect_description,
    detect_gallery as dom_detect_gallery,
    detect_image as dom_detect_image,
    detect_price as dom_detect_price,
    detect_sku as dom_detect_sku,
    detect_title as dom_detect_title,
    detect_url as dom_detect_url,
    detect_weight as dom_detect_weight,
)


_price_detector = PriceDetector()
_image_detector = ImageDetector()
_link_detector = LinkDetector()
_product_detector = ProductDetector()

_NOISE_TERMS = [
    "add to cart",
    "added successfully",
    "loading",
    "veuillez patienter",
    "ajoute au panier",
    "ajoutee au panier",
    "checkout",
    "panier",
    "quantity selector",
]

_NOISE_PATTERN = re.compile("|".join(re.escape(t) for t in _NOISE_TERMS), re.I)
_QTY_PATTERN = re.compile(r"\b(?:qty|quantity|qte|quantite|x)\s*[:x-]?\s*\d+\b", re.I)

_FIELD_WEIGHTS: dict[str, float] = {
    "title": 0.16,
    "price": 0.15,
    "compare_at_price": 0.09,
    "image": 0.08,
    "gallery": 0.08,
    "description": 0.10,
    "sku": 0.08,
    "ean": 0.08,
    "brand": 0.07,
    "category": 0.06,
    "stock": 0.08,
    "tags": 0.07,
}

_STRATEGY_RELIABILITY: dict[str, float] = {
    "jsonld": 0.95,
    "schema": 0.90,
    "opengraph": 0.75,
    "meta": 0.65,
    "api": 0.82,
    "dom": 0.62,
    "css": 0.57,
}


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    text = str(value)
    text = _NOISE_PATTERN.sub(" ", text)
    text = _QTY_PATTERN.sub(" ", text)
    text = re.sub(r"\b\d+\s*(?:pcs?|pieces?|items?)\b", " ", text, flags=re.I)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _clean_text(value: str | None) -> str:
    return clean_text(value)


def detect_title(raw: dict[str, Any], fallback_text: str = "") -> str:
    for key in ("title", "name", "headline", "displayName", "display_name"):
        value = raw.get(key)
        if isinstance(value, str):
            title = clean_text(value)
            if title:
                return title
    return clean_text(fallback_text)


def detect_description(card, page_soup=None):
    return dom_detect_description(card, page_soup=page_soup)


def detect_compare_price(card):
    return dom_detect_compare_price(card, _price_detector)


def detect_gallery(card, base_url: str = ""):
    return dom_detect_gallery(card, _image_detector, base_url=base_url)


def detect_brand(card):
    return dom_detect_brand(card)


def detect_weight(card):
    return dom_detect_weight(card)


def detect_category(card):
    return dom_detect_category(card)


def detect_url(card, base_url: str = ""):
    return dom_detect_url(card, _link_detector, base_url=base_url)


def detect_sku(card):
    return dom_detect_sku(card)


def detect_barcode(card):
    return dom_detect_barcode(card)


def detect_price(raw: dict[str, Any], fallback_text: str = "") -> float | None:
    for key in ("price", "currentPrice", "salePrice", "unit_price", "final_price", "amount", "value"):
        parsed = _parse_price(str(raw.get(key) or ""))
        if parsed is not None:
            return parsed
    for nested_key in ("offers", "pricing", "priceInfo", "price_data"):
        nested = raw.get(nested_key)
        if isinstance(nested, dict):
            for key in ("price", "current", "amount", "value", "salePrice"):
                parsed = _parse_price(str(nested.get(key) or ""))
                if parsed is not None:
                    return parsed
    return _price_detector.detect_in_text(clean_text(fallback_text))


def detect_image(raw: dict[str, Any], base_url: str = "") -> tuple[str, list[str]]:
    gallery = _collect_images(raw, base_url)
    return (gallery[0] if gallery else "", gallery)


def _sanitize_soup(soup: BeautifulSoup) -> BeautifulSoup:
    if soup is None:
        return BeautifulSoup("", "lxml")

    # Remove purely interactive/non-content elements from extraction text.
    for tag in soup.select("button, form, input, select, textarea, svg, script, noscript"):
        tag.decompose()

    # Remove hidden/accessibility helper nodes and common cart/quantity widgets.
    for tag in soup.select(
        "[hidden], [aria-hidden='true'], [type='hidden'], [style*='display:none'], [style*='visibility:hidden'], "
        "[class*='quantity' i], [id*='quantity' i], [class*='add-to-cart' i], [id*='add-to-cart' i], [class*='checkout' i], [id*='checkout' i], "
        "[class*='basket' i], [class*='cart' i], [id*='cart' i]"
    ):
        tag.decompose()

    return soup


def _parse_price(value: str | None) -> float | None:
    return _price_detector.parse_price(value)


def _normalize_url(url: str, base_url: str = "") -> str:
    return _link_detector.normalize(url, base_url)


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        clean = _clean_text(value)
        return [clean] if clean else []
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            if isinstance(item, str):
                clean = _clean_text(item)
                if clean and clean not in out:
                    out.append(clean)
            elif isinstance(item, dict):
                for key in ("name", "title", "url"):
                    candidate = item.get(key)
                    if isinstance(candidate, str):
                        clean = _clean_text(candidate)
                        if clean and clean not in out:
                            out.append(clean)
                        break
        return out
    if isinstance(value, dict):
        for key in ("name", "title", "url"):
            candidate = value.get(key)
            if isinstance(candidate, str):
                clean = _clean_text(candidate)
                return [clean] if clean else []
    return []


def _split_tags(value: Any) -> list[str]:
    if isinstance(value, list):
        return [t for t in (_clean_text(v) for v in value if isinstance(v, str)) if t]
    if isinstance(value, str):
        parts = re.split(r"[,;|]", value)
        tags: list[str] = []
        for part in parts:
            tag = _clean_text(part)
            if tag and tag.lower() not in {t.lower() for t in tags}:
                tags.append(tag)
        return tags
    return []


def _to_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        text = value.strip().lower()
        if not text:
            return None
        if text in {"in stock", "instock", "available", "available now", "true", "yes"}:
            return 1
        if text in {"out of stock", "outofstock", "unavailable", "false", "no"}:
            return 0
        match = re.search(r"-?\d+", text)
        if match:
            try:
                return int(match.group(0))
            except ValueError:
                return None
    return None


def _extract_sku(text: str) -> str:
    if not text:
        return ""
    match = re.search(r"\b(?:sku|ref|reference|item\s*id)\s*[:#-]?\s*([A-Za-z0-9._-]{3,})\b", text, re.I)
    return _clean_text(match.group(1)) if match else ""


def _extract_ean(text: str) -> str:
    if not text:
        return ""
    match = re.search(r"\b(?:ean|gtin|barcode)\s*[:#-]?\s*(\d{8,14})\b", text, re.I)
    return _clean_text(match.group(1)) if match else ""


def _first_str(raw: dict[str, Any], keys: list[str]) -> str:
    for key in keys:
        value = raw.get(key)
        if isinstance(value, str):
            clean = _clean_text(value)
            if clean:
                return clean
    return ""


def _collect_images(raw: dict[str, Any], base_url: str = "") -> list[str]:
    values: list[str] = []
    for key in ("gallery", "images", "image", "thumbnail", "thumbnailUrl"):
        entries = _as_list(raw.get(key))
        for entry in entries:
            normalized = _image_detector.normalize(entry, base_url)
            if normalized and normalized not in values:
                values.append(normalized)
    return values


def _normalize_item(raw: dict[str, Any], source: str, base_url: str = "") -> dict[str, Any]:
    combined_text = " ".join(
        [
            _first_str(raw, ["title", "name", "headline", "displayName"]),
            _first_str(raw, ["description", "subtitle", "summary"]),
            _first_str(raw, ["category", "categoryName"]),
            _first_str(raw, ["keywords", "tags_text"]),
        ]
    )
    title = detect_title(raw)
    description = _first_str(raw, ["description", "subtitle", "summary"])
    url = _normalize_url(_first_str(raw, ["url", "link", "canonical", "productUrl"]), base_url)

    image, images = detect_image(raw, base_url)
    price = detect_price(raw, fallback_text=description)
    if price is None and description:
        price = _price_detector.detect_in_text(description)

    compare_at_price = _parse_price(
        str(
            raw.get("compare_at_price")
            or raw.get("old_price")
            or raw.get("listPrice")
            or raw.get("msrp")
            or raw.get("highPrice")
            or ""
        )
    )

    sku = _first_str(raw, ["sku", "productId", "id", "itemId"])
    if not sku:
        sku = _extract_sku(combined_text)

    ean = _first_str(raw, ["ean", "gtin", "gtin13", "gtin12", "barcode"])
    if not ean:
        ean = _extract_ean(combined_text)

    brand = _first_str(raw, ["brand", "manufacturer"])
    category = _first_str(raw, ["category", "categoryName"])

    stock = _to_int(raw.get("stock"))
    if stock is None:
        stock = _to_int(raw.get("availability"))

    tags = _split_tags(raw.get("tags") or raw.get("keywords") or raw.get("tag"))

    return {
        "title": title,
        "price": price,
        "compare_at_price": compare_at_price,
        "currency": _first_str(raw, ["currency", "priceCurrency"]),
        "image": image,
        "images": images,
        "gallery": images,
        "description": clean_text(description),
        "sku": sku,
        "ean": ean,
        "barcode": ean,
        "brand": brand,
        "category": category,
        "stock": stock,
        "tags": tags,
        "weight": _parse_price(str(raw.get("weight") or raw.get("netWeight") or raw.get("grossWeight") or "")),
        "url": url,
        "source": source,
        "_field_confidence": raw.get("_field_confidence") if isinstance(raw.get("_field_confidence"), dict) else {},
        "_field_methods": raw.get("_field_methods") if isinstance(raw.get("_field_methods"), dict) else {},
    }


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return len(value) > 0
    return True


def _score_item(item: dict[str, Any], source: str) -> tuple[float, dict[str, float]]:
    reliability = _STRATEGY_RELIABILITY.get(source, 0.5)
    denominator = sum(_FIELD_WEIGHTS.values()) or 1.0
    field_scores: dict[str, float] = {}
    dom_field_conf = item.get("_field_confidence") if isinstance(item.get("_field_confidence"), dict) else {}
    score = 0.0
    for field, weight in _FIELD_WEIGHTS.items():
        present = _has_value(item.get(field))
        dom_hint = float(dom_field_conf.get(field) or 0.0)
        if dom_hint > 0:
            rel = max(min(dom_hint, 1.0), reliability * 0.5)
        else:
            rel = reliability
        field_score = round(weight * rel if present else 0.0, 4)
        field_scores[field] = field_score
        score += field_score
    normalized = round(min(score / denominator, 1.0), 4)
    return normalized, field_scores


def _identity_key(item: dict[str, Any]) -> str:
    title = _clean_text(str(item.get("title") or "")).lower()
    if title:
        return f"title:{title}"
    if item.get("sku"):
        return f"sku:{str(item['sku']).lower()}"
    if item.get("ean"):
        return f"ean:{str(item['ean']).lower()}"
    if item.get("url"):
        return f"url:{str(item['url']).lower()}"
    return "title:"


def _merge_items(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not candidates:
        return []

    grouped: dict[str, list[dict[str, Any]]] = {}
    for candidate in candidates:
        key = _identity_key(candidate)
        if key in {"title:"}:
            continue
        grouped.setdefault(key, []).append(candidate)

    merged: list[dict[str, Any]] = []
    for items in grouped.values():
        base = {
            "title": "",
            "price": None,
            "compare_at_price": None,
            "currency": "",
            "image": "",
            "images": [],
            "gallery": [],
            "description": "",
            "sku": "",
            "ean": "",
            "barcode": "",
            "brand": "",
            "category": "",
            "stock": None,
            "tags": [],
            "url": "",
            "source": [],
            "confidence": 0.0,
            "confidence_by_field": {},
            "methods_by_field": {},
        }

        best_field_score: dict[str, float] = {field: -1.0 for field in _FIELD_WEIGHTS}
        best_field_method: dict[str, str] = {field: "" for field in _FIELD_WEIGHTS}
        galleries: list[str] = []
        tags: list[str] = []

        for item in items:
            score = float(item.get("confidence") or 0.0)
            if score > base["confidence"]:
                base["confidence"] = score

            source = str(item.get("source") or "")
            if source and source not in base["source"]:
                base["source"].append(source)

            field_scores = item.get("confidence_by_field") or {}
            field_methods = item.get("_field_methods") or {}
            for field in _FIELD_WEIGHTS:
                candidate_value = item.get(field)
                candidate_field_score = float(field_scores.get(field) or 0.0)
                if _has_value(candidate_value) and candidate_field_score >= best_field_score[field]:
                    base[field] = candidate_value
                    best_field_score[field] = candidate_field_score
                    best_field_method[field] = str(field_methods.get(field) or item.get("source") or "")

            for img in item.get("gallery") or []:
                if img and img not in galleries:
                    galleries.append(img)
            for tag in item.get("tags") or []:
                if tag and tag.lower() not in {t.lower() for t in tags}:
                    tags.append(tag)

        base["gallery"] = galleries
        base["images"] = galleries
        if not base.get("image") and galleries:
            base["image"] = galleries[0]
        base["tags"] = tags
        base["barcode"] = str(base.get("ean") or base.get("barcode") or "")

        best_for_non_weighted = sorted(items, key=lambda i: float(i.get("confidence") or 0.0), reverse=True)
        for candidate in best_for_non_weighted:
            candidate_url = _clean_text(str(candidate.get("url") or ""))
            if candidate_url:
                base["url"] = candidate_url
                break
        for candidate in best_for_non_weighted:
            candidate_currency = _clean_text(str(candidate.get("currency") or ""))
            if candidate_currency:
                base["currency"] = candidate_currency
                break

        base["source"] = ",".join(base["source"])
        base["confidence_by_field"] = {k: round(max(v, 0.0), 4) for k, v in best_field_score.items()}
        base["methods_by_field"] = best_field_method
        merged.append(base)

    merged.sort(key=lambda i: float(i.get("confidence") or 0.0), reverse=True)
    return merged


def _extract_jsonld_data(html: str, base_url: str = "") -> list[dict[str, Any]]:
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
                offers = item.get("offers") if isinstance(item.get("offers"), dict) else {}
                brand = item.get("brand")
                if isinstance(brand, dict):
                    brand = brand.get("name")
                product = {
                    "title": _clean_text(item.get("name") or item.get("headline") or item.get("title") or ""),
                    "description": _clean_text(item.get("description") or ""),
                    "url": item.get("url") or "",
                    "sku": _clean_text(item.get("sku") or ""),
                    "ean": _clean_text(item.get("gtin13") or item.get("gtin12") or item.get("gtin") or item.get("barcode") or ""),
                    "price": _parse_price(str(offers.get("price") or item.get("price") or "")),
                    "compare_at_price": _parse_price(str(offers.get("highPrice") or item.get("highPrice") or "")),
                    "currency": offers.get("priceCurrency") or item.get("priceCurrency"),
                    "images": item.get("image") if isinstance(item.get("image"), list) else ([item.get("image")] if item.get("image") else []),
                    "brand": _clean_text(brand if isinstance(brand, str) else ""),
                    "category": _clean_text(item.get("category") or ""),
                    "stock": _to_int(offers.get("availability") or item.get("availability")),
                    "tags": _split_tags(item.get("keywords") or item.get("tags") or ""),
                }
                products.append(_normalize_item(product, source="jsonld", base_url=base_url))

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

            offers = item.get("offers") if isinstance(item.get("offers"), dict) else {}
            product = {
                "title": _clean_text(item.get("name") or item.get("title") or item.get("displayName") or ""),
                "description": _clean_text(item.get("description") or item.get("subtitle") or ""),
                "url": item.get("url") or item.get("productUrl") or "",
                "sku": _clean_text(item.get("sku") or item.get("productId") or item.get("id") or ""),
                "ean": _clean_text(item.get("ean") or item.get("gtin") or item.get("barcode") or ""),
                "price": _parse_price(str(offers.get("price") or item.get("price") or item.get("currentPrice") or "")),
                "compare_at_price": _parse_price(str(item.get("compare_at_price") or item.get("oldPrice") or item.get("listPrice") or "")),
                "currency": _clean_text(str(offers.get("priceCurrency") or item.get("priceCurrency") or "")),
                "images": item.get("images") or item.get("image") or item.get("media") or [],
                "brand": _clean_text(item.get("brand") or item.get("manufacturer") or ""),
                "category": _clean_text(item.get("category") or item.get("categoryName") or ""),
                "stock": _to_int(item.get("stock") or item.get("availability")),
                "tags": item.get("tags") or item.get("keywords") or [],
            }
            products.append(product)

    return products


def _extract_embedded_json_payloads(html: str) -> list[Any]:
    soup = BeautifulSoup(html or "", "lxml")
    payloads: list[Any] = []

    for script in soup.find_all("script"):
        script_type = (script.get("type") or "").lower()
        script_id = (script.get("id") or "").lower()
        raw = script.string or script.get_text() or ""
        text = raw.strip()
        if not text:
            continue

        likely_json = (
            "json" in script_type
            or script_id in {"__next_data__", "__nuxt", "__initial_state__"}
            or text.startswith("{")
            or text.startswith("[")
        )
        if not likely_json:
            continue

        if len(text) > 4_000_000:
            continue

        try:
            payload = json.loads(text)
        except Exception:
            continue

        if isinstance(payload, (dict, list)):
            payloads.append(payload)

    return payloads


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
            "images": [_image_detector.normalize(image, base_url)] if image else [],
            "brand": _clean_text(brand_tag.get_text(" ", strip=True) if brand_tag else ""),
            "ean": _clean_text((card.select_one("[itemprop='gtin13'], [itemprop='gtin12'], [itemprop='gtin'], [itemprop='barcode']") or {}).get_text(" ", strip=True) if card.select_one("[itemprop='gtin13'], [itemprop='gtin12'], [itemprop='gtin'], [itemprop='barcode']") else ""),
            "stock": _to_int((card.select_one("[itemprop='availability']") or {}).get("content") if card.select_one("[itemprop='availability']") else None),
            "tags": _split_tags((card.select_one("[itemprop='keywords']") or {}).get_text(" ", strip=True) if card.select_one("[itemprop='keywords']") else ""),
        }
        if product["title"] or product["url"]:
            products.append(_normalize_item(product, source="schema", base_url=base_url))
    return products


def _extract_opengraph_products(soup: BeautifulSoup, base_url: str = "") -> list[dict[str, Any]]:
    def get_meta(*keys: str) -> str:
        for key in keys:
            node = soup.find("meta", attrs={"property": key}) or soup.find("meta", attrs={"name": key})
            if node and node.get("content"):
                value = _clean_text(node.get("content"))
                if value:
                    return value
        return ""

    title = get_meta("og:title", "twitter:title")
    description = get_meta("og:description", "description", "twitter:description")
    image = get_meta("og:image", "twitter:image")
    url = get_meta("og:url", "twitter:url", "canonical")
    price = _parse_price(get_meta("product:price:amount", "og:price:amount", "price"))
    compare_at_price = _parse_price(get_meta("product:original_price:amount", "product:old_price:amount", "old_price"))
    sku = get_meta("product:retailer_item_id", "product:sku", "sku")
    ean = get_meta("product:ean", "product:gtin", "ean", "barcode")
    brand = get_meta("product:brand", "brand")
    category = get_meta("product:category", "category")
    availability = get_meta("product:availability", "availability")
    tags = _split_tags(get_meta("article:tag", "keywords"))

    if not any([title, price is not None, image, sku, ean]):
        return []

    product = _normalize_item(
        {
            "title": title,
            "description": description,
            "image": image,
            "url": url,
            "price": price,
            "compare_at_price": compare_at_price,
            "sku": sku,
            "ean": ean,
            "brand": brand,
            "category": category,
            "stock": availability,
            "tags": tags,
        },
        source="opengraph",
        base_url=base_url,
    )
    return [product]


def _extract_meta_products(soup: BeautifulSoup, base_url: str = "") -> list[dict[str, Any]]:
    metas = soup.find_all("meta")
    bucket: dict[str, Any] = {}
    for meta in metas:
        key = _clean_text(meta.get("name") or meta.get("property") or "").lower()
        value = _clean_text(meta.get("content") or "")
        if not key or not value:
            continue
        if any(token in key for token in ["title", "product:name"]):
            bucket.setdefault("title", value)
        elif any(token in key for token in ["description", "summary"]):
            bucket.setdefault("description", value)
        elif any(token in key for token in ["image", "thumbnail"]):
            bucket.setdefault("image", value)
        elif "price" in key:
            if "old" in key or "original" in key or "compare" in key:
                bucket.setdefault("compare_at_price", value)
            else:
                bucket.setdefault("price", value)
        elif "sku" in key:
            bucket.setdefault("sku", value)
        elif any(token in key for token in ["ean", "gtin", "barcode"]):
            bucket.setdefault("ean", value)
        elif "brand" in key:
            bucket.setdefault("brand", value)
        elif "category" in key:
            bucket.setdefault("category", value)
        elif "stock" in key or "availability" in key:
            bucket.setdefault("stock", value)
        elif "keyword" in key or "tag" in key:
            bucket.setdefault("tags", value)

    if not bucket:
        return []
    return [_normalize_item(bucket, source="meta", base_url=base_url)]


def _extract_css_products(soup: BeautifulSoup, base_url: str = "") -> list[dict[str, Any]]:
    selectors = [
        ".product",
        ".product-card",
        ".product-item",
        ".item",
        ".card",
        "[class*='product']",
    ]
    products: list[dict[str, Any]] = []
    seen: set[str] = set()
    for selector in selectors:
        for node in soup.select(selector):
            title_node = node.select_one("h1, h2, h3, [class*='title'], [itemprop='name']")
            link_node = node.select_one("a[href]")
            desc_node = node.select_one("p, [class*='desc'], [itemprop='description']")

            title = _clean_text(title_node.get_text(" ", strip=True) if title_node else "")
            description = _clean_text(desc_node.get_text(" ", strip=True) if desc_node else node.get_text(" ", strip=True))
            url = _normalize_url(link_node.get("href") if link_node else "", base_url)
            price = _price_detector.detect_in_text(description)
            images = _image_detector.extract_from_node(node, base_url)

            if not any([title, url, price is not None, images]):
                continue

            raw = {
                "title": title,
                "description": description,
                "url": url,
                "price": price,
                "images": images,
                "sku": _extract_sku(description),
                "ean": _extract_ean(description),
            }
            normalized = _normalize_item(raw, source="css", base_url=base_url)
            key = _identity_key(normalized)
            if key in seen:
                continue
            seen.add(key)
            products.append(normalized)
        if products:
            break
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
    title = _clean_text(
        item.get("name")
        or item.get("title")
        or item.get("displayName")
        or item.get("display_name")
        or ""
    )
    sku_like = _clean_text(
        item.get("sku")
        or item.get("id")
        or item.get("productId")
        or item.get("product_id")
        or ""
    )
    has_price = _extract_price_from_item(item) is not None
    has_image = bool(_extract_images_from_item(item))

    if not title:
        return False

    if has_price or has_image:
        return True

    # `productId` and `id` are weak signals on their own: require a specific title
    # so generic container nodes do not get promoted as products.
    if sku_like:
        generic_title = title.lower()
        generic_tokens = {
            "product",
            "products",
            "item",
            "items",
            "catalog",
            "category",
            "collection",
            "shop",
            "home",
            "menu",
        }
        word_count = len([part for part in generic_title.split() if part])
        if generic_title in generic_tokens or word_count < 2:
            return False
        return True

    return False


class UniversalParser:

    def parse(self, html: str, base_url: str = "") -> list[dict[str, Any]]:
        if not html:
            return []
        soup = _sanitize_soup(BeautifulSoup(html, "lxml"))

        strategy_candidates: list[dict[str, Any]] = []

        strategy_products = _extract_jsonld_data(html, base_url)
        strategy_candidates.extend(strategy_products)

        strategy_products = _extract_schema_microdata_products(soup, base_url)
        strategy_candidates.extend(strategy_products)

        strategy_products = _extract_opengraph_products(soup, base_url)
        strategy_candidates.extend(strategy_products)

        strategy_products = _extract_meta_products(soup, base_url)
        strategy_candidates.extend(strategy_products)

        for item in _extract_application_json_data(html):
            strategy_candidates.append(_normalize_item(item, source="api", base_url=base_url))

        for item in _extract_dom_products(soup, base_url):
            strategy_candidates.append(_normalize_item(item, source="dom", base_url=base_url))

        strategy_candidates.extend(_extract_css_products(soup, base_url))

        if not strategy_candidates:
            for item in _extract_link_based_products(soup, base_url):
                strategy_candidates.append(_normalize_item(item, source="css", base_url=base_url))

        scored: list[dict[str, Any]] = []
        for item in strategy_candidates:
            source = str(item.get("source") or "dom")
            confidence, confidence_by_field = _score_item(item, source)
            item["confidence"] = confidence
            item["confidence_by_field"] = confidence_by_field
            # Keep parser output clean and focused on product fields.
            item["title"] = clean_text(str(item.get("title") or ""))
            item["description"] = clean_text(str(item.get("description") or ""))
            item["sku"] = clean_text(str(item.get("sku") or ""))
            item["barcode"] = clean_text(str(item.get("barcode") or item.get("ean") or ""))
            scored.append(item)

        return _merge_items(scored)

    def parse_products(self, html: str, base_url: str = "") -> list[Product]:
        items = self.parse(html, base_url)
        products: list[Product] = []
        for item in items:
            images = item.get("gallery") or item.get("images") or []
            image = images[0] if images else ""
            products.append(
                Product(
                    title=clean_text(item.get("title") or ""),
                    description=clean_text(item.get("description") or ""),
                    price=item.get("price"),
                    compare_at_price=item.get("compare_at_price"),
                    currency=clean_text(item.get("currency") or ""),
                    sku=clean_text(item.get("sku") or ""),
                    ean=clean_text(item.get("ean") or ""),
                    barcode=clean_text(item.get("barcode") or item.get("ean") or ""),
                    brand=clean_text(item.get("brand") or ""),
                    category=clean_text(item.get("category") or ""),
                    weight=item.get("weight") if isinstance(item.get("weight"), (int, float)) else None,
                    image=image,
                    gallery=images,
                    stock=item.get("stock") if isinstance(item.get("stock"), int) else None,
                    tags=item.get("tags") if isinstance(item.get("tags"), list) else [],
                    url=clean_text(item.get("url") or ""),
                    confidence=float(item.get("confidence")) if isinstance(item.get("confidence"), (int, float)) else None,
                    confidence_by_field=item.get("confidence_by_field") if isinstance(item.get("confidence_by_field"), dict) else {},
                    methods_by_field=item.get("methods_by_field") if isinstance(item.get("methods_by_field"), dict) else {},
                )
            )
        return products

    def parse_api_payloads(self, payloads: list[Any]) -> list[Product]:
        normalized_items: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for payload in payloads or []:
            for item in _iter_dict_nodes(payload):
                if not _is_product_like(item):
                    continue
                title = _clean_text(
                    item.get("name")
                    or item.get("title")
                    or item.get("displayName")
                    or item.get("display_name")
                    or ""
                )
                images = _extract_images_from_item(item)
                url = item.get("url") or item.get("productUrl") or item.get("product_url") or ""
                sku = _clean_text(item.get("sku") or item.get("productId") or item.get("product_id") or item.get("id") or "")

                dedupe_key = (title.lower(), sku or url)
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)

                normalized = _normalize_item(
                    {
                        "title": title,
                        "description": _clean_text(item.get("description") or item.get("subtitle") or ""),
                        "price": _extract_price_from_item(item),
                        "compare_at_price": _parse_price(str(item.get("compare_at_price") or item.get("oldPrice") or "")),
                        "sku": sku,
                        "ean": _clean_text(item.get("ean") or item.get("gtin") or item.get("barcode") or ""),
                        "brand": _clean_text(item.get("brand") or item.get("manufacturer") or ""),
                        "category": _clean_text(item.get("category") or item.get("categoryName") or ""),
                        "images": images,
                        "stock": item.get("stock") if isinstance(item.get("stock"), int) else item.get("availability"),
                        "tags": item.get("tags") if isinstance(item.get("tags"), list) else item.get("keywords") or [],
                        "url": url,
                    },
                    source="api",
                )
                confidence, confidence_by_field = _score_item(normalized, "api")
                normalized["confidence"] = confidence
                normalized["confidence_by_field"] = confidence_by_field
                normalized_items.append(normalized)

        products: list[Product] = []
        for item in _merge_items(normalized_items):
            images = item.get("gallery") or []
            products.append(
                Product(
                    title=item.get("title") or "",
                    description=item.get("description") or "",
                    price=item.get("price"),
                    compare_at_price=item.get("compare_at_price"),
                    currency=item.get("currency") or "",
                    sku=item.get("sku") or "",
                    ean=item.get("ean") or "",
                    barcode=item.get("barcode") or item.get("ean") or "",
                    brand=item.get("brand") or "",
                    category=item.get("category") or "",
                    image=images[0] if images else "",
                    gallery=images,
                    stock=item.get("stock") if isinstance(item.get("stock"), int) else None,
                    tags=item.get("tags") if isinstance(item.get("tags"), list) else [],
                    url=item.get("url") or "",
                    confidence=float(item.get("confidence")) if isinstance(item.get("confidence"), (int, float)) else None,
                    confidence_by_field=item.get("confidence_by_field") if isinstance(item.get("confidence_by_field"), dict) else {},
                    methods_by_field=item.get("methods_by_field") if isinstance(item.get("methods_by_field"), dict) else {},
                )
            )
        return products

    def parse_embedded_payloads(self, html: str) -> list[Product]:
        payloads = _extract_embedded_json_payloads(html)
        if not payloads:
            return []
        return self.parse_api_payloads(payloads)
