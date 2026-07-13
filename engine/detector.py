from urllib.parse import urlparse

from engine.html_engine import HtmlEngine
from engine.playwright_engine import PlaywrightEngine


class Detector:

    def detect(self, url):

        host = urlparse(url).netloc.lower()

        javascript_sites = [
            "yango",
            "shufersal",
            "tavlineypereg",
            "shopify",
            "wixsite",
            "magento"
        ]

        for site in javascript_sites:

            if site in host:
                return PlaywrightEngine()

        return HtmlEngine()