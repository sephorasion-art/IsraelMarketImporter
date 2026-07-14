from __future__ import annotations

from typing import Any

from engine.models import Product


class ApiDiscoveryEngine:
    """Generic API discovery and JSON-to-Product extraction engine."""

    URL_TOKENS = ("/api/", "graphql", ".json", "ajax", "catalog", "products", "search")

    def classify_url(self, url: str, resource_type: str = "") -> list[str]:
        labels: list[str] = []
        lower_url = (url or "").lower()
        rt = (resource_type or "").lower()

        if rt == "fetch":
            labels.append("fetch")
        if rt == "xhr":
            labels.append("xhr")
        if "graphql" in lower_url:
            labels.append("graphql")
        if ".json" in lower_url or "format=json" in lower_url:
            labels.append("json")
        if any(token in lower_url for token in self.URL_TOKENS):
            labels.append("api")

        dedup: list[str] = []
        for label in labels:
            if label not in dedup:
                dedup.append(label)
        return dedup

    def discover_api_urls(self, events: list[dict[str, str]]) -> list[str]:
        urls: list[str] = []
        for event in events or []:
            url = event.get("url") or ""
            labels = event.get("labels") or ""
            if not url:
                continue
            if labels or any(token in url.lower() for token in self.URL_TOKENS):
                if url not in urls:
                    urls.append(url)
        return urls

    def discover_products(self, payloads: list[Any]) -> list[Product]:
        products: list[Product] = []
        seen: set[tuple[str, str]] = set()

        for payload in payloads or []:
            for node in self._iter_nodes(payload):
                if not isinstance(node, dict):
                    continue
                if not self._is_product_like(node):
                    continue
                product = self._to_product(node)
                key = (product.title.lower(), (product.sku or product.url or "").lower())
                if key in seen:
                    continue
                seen.add(key)
                products.append(product)
        return products

    def _iter_nodes(self, payload: Any):
        if isinstance(payload, dict):
            yield payload
            for value in payload.values():
                yield from self._iter_nodes(value)
        elif isinstance(payload, list):
            for value in payload:
                yield from self._iter_nodes(value)

    @staticmethod
    def _is_product_like(node: dict[str, Any]) -> bool:
        keys = {str(k).lower() for k in node.keys()}
        has_name = "title" in keys or "name" in keys
        has_price = "price" in keys or "currentprice" in keys or "saleprice" in keys
        has_image = "image" in keys or "images" in keys or "thumbnail" in keys
        has_id = "sku" in keys or "id" in keys or "productid" in keys
        has_category = "category" in keys or "categoryname" in keys

        score = sum([has_name, has_price, has_image, has_id, has_category])
        return bool(has_name and score >= 3)

    @staticmethod
    def _to_list_images(value: Any) -> list[str]:
        if isinstance(value, str):
            return [value] if value else []
        if isinstance(value, dict):
            url = value.get("url")
            return [url] if isinstance(url, str) and url else []
        if isinstance(value, list):
            images: list[str] = []
            for entry in value:
                if isinstance(entry, str) and entry and entry not in images:
                    images.append(entry)
                elif isinstance(entry, dict):
                    url = entry.get("url")
                    if isinstance(url, str) and url and url not in images:
                        images.append(url)
            return images
        return []

    @staticmethod
    def _to_float(value: Any) -> float | None:
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            cleaned = value.replace(" ", "").replace(",", ".")
            cleaned = "".join(ch for ch in cleaned if ch.isdigit() or ch in ".-")
            if not cleaned:
                return None
            try:
                return float(cleaned)
            except ValueError:
                return None
        return None

    def _to_product(self, node: dict[str, Any]) -> Product:
        title = str(node.get("title") or node.get("name") or node.get("displayName") or "").strip()
        description = str(node.get("description") or node.get("subtitle") or "").strip()
        price = self._to_float(node.get("price") or node.get("currentPrice") or node.get("salePrice"))
        compare_at_price = self._to_float(node.get("oldPrice") or node.get("compare_at_price") or node.get("listPrice"))
        sku = str(node.get("sku") or node.get("productId") or node.get("id") or "").strip()
        barcode = str(node.get("ean") or node.get("gtin") or node.get("barcode") or "").strip()
        brand = str(node.get("brand") or node.get("manufacturer") or "").strip()
        category = str(node.get("category") or node.get("categoryName") or "").strip()
        url = str(node.get("url") or node.get("productUrl") or "").strip()

        images = self._to_list_images(node.get("images") or node.get("image") or node.get("thumbnail"))
        tags_raw = node.get("tags") or node.get("keywords") or []
        if isinstance(tags_raw, str):
            tags = [part.strip() for part in tags_raw.split(",") if part.strip()]
        elif isinstance(tags_raw, list):
            tags = [str(t).strip() for t in tags_raw if str(t).strip()]
        else:
            tags = []

        stock = node.get("stock")
        if not isinstance(stock, int):
            stock = None

        return Product(
            title=title,
            description=description,
            price=price,
            compare_at_price=compare_at_price,
            sku=sku,
            barcode=barcode,
            brand=brand,
            category=category,
            image=images[0] if images else "",
            gallery=images,
            stock=stock,
            tags=tags,
            url=url,
        )
