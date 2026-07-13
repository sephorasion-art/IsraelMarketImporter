from urllib.parse import urlparse


class Detector:

    def detect(self, url: str):

        host = urlparse(url).netloc.lower()

        if "shopify" in host:
            return "shopify"

        if "woocommerce" in host:
            return "woocommerce"

        if "yango" in host:
            return "playwright"

        if "tavlineypereg" in host:
            return "playwright"

        if "shufersal" in host:
            return "playwright"

        return "html"