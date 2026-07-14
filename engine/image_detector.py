from __future__ import annotations

from urllib.parse import urljoin


class ImageDetector:
    """Extract and normalize image URLs from DOM nodes."""

    def normalize(self, url: str, base_url: str = "") -> str:
        if not url:
            return ""
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("/") and base_url:
            return urljoin(base_url, url)
        return url

    def extract_from_node(self, node, base_url: str = "") -> list[str]:
        images: list[str] = []
        for img in node.select("img"):
            src = img.get("src") or img.get("data-src") or ""
            src = self.normalize(src, base_url)
            if src and src not in images:
                images.append(src)
        return images
