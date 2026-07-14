from __future__ import annotations

import re
from urllib.parse import urlparse


class CmsDetector:
    """Detect the underlying commerce CMS from host and markup."""

    def detect(self, url: str, html: str) -> str:
        host = urlparse(url).netloc.lower()
        body = html or ""

        if self._is_shopify(host, body):
            return "shopify"
        if self._is_woocommerce(host, body):
            return "woocommerce"
        if self._is_magento(host, body):
            return "magento"
        if self._is_prestashop(host, body):
            return "prestashop"
        if self._is_bigcommerce(host, body):
            return "bigcommerce"
        if self._is_wix(host, body):
            return "wix"
        if self._is_opencart(host, body):
            return "opencart"
        if self._is_squarespace(host, body):
            return "squarespace"
        return "unknown"

    def _is_shopify(self, host: str, body: str) -> bool:
        return bool(
            host.endswith(".shopify.com")
            or host == "shopify.com"
            or host.endswith(".myshopify.com")
            or "cdn.shopify.com" in host
            or "cdn.shopify.com" in body
            or "Shopify.theme" in body
        )

    def _is_woocommerce(self, host: str, body: str) -> bool:
        return bool(re.search(r"woocommerce|wp-content/plugins/woocommerce|wc-add-to-cart", f"{host} {body}", re.I))

    def _is_magento(self, host: str, body: str) -> bool:
        return bool(re.search(r"mage\.init|Magento\.config|Magento\.Setup", f"{host} {body}", re.I))

    def _is_prestashop(self, host: str, body: str) -> bool:
        return bool(re.search(r"prestashop|var\s+prestashop", f"{host} {body}", re.I))

    def _is_bigcommerce(self, host: str, body: str) -> bool:
        return bool(re.search(r"bigcommerce|stencil|cdn\d+\.bigcommerce", f"{host} {body}", re.I))

    def _is_wix(self, host: str, body: str) -> bool:
        return bool(re.search(r"wixsite|wix\.com|wix_apps|WixLoader", f"{host} {body}", re.I))

    def _is_opencart(self, host: str, body: str) -> bool:
        return bool(re.search(r"index\.php\?route=|opencart", f"{host} {body}", re.I))

    def _is_squarespace(self, host: str, body: str) -> bool:
        return bool(re.search(r"squarespace|static\.squarespace", f"{host} {body}", re.I))
