import pytest

from engine.detector import Detector


def test_detector_known_hosts():
    d = Detector()

    assert d.detect("https://www.tavlineypereg.co.il") == "playwright"
    assert d.detect("https://deli.yango.com/en-il/catalog/grocery/category/snacks") == "playwright"
    assert d.detect("https://example.com") == "html"
    assert d.detect("https://myshop.shopify.com") == "shopify"
    assert d.detect("https://store.woocommerce.com") == "woocommerce"
