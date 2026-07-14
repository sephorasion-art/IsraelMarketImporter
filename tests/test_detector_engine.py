from engine.detector import Detector


def test_detector_shopify():
    detector = Detector()
    assert detector.detect("https://example.myshopify.com") == "shopify"
    assert detector.detect("https://cdn.shopify.com/s/files/.../file.css") == "shopify"


def test_detector_woocommerce():
    detector = Detector()
    html = "<html><head></head><body>wp-content/plugins/woocommerce</body></html>"
    assert detector.detect("https://example.com", html) == "woocommerce"


def test_detector_nextjs_and_react():
    detector = Detector()
    html = '<div id="__next"></div><script id="__NEXT_DATA__">{}</script>'
    assert detector.detect("https://example.com", html) == "nextjs"

    html = '<div data-reactroot=""></div>'
    assert detector.detect("https://example.com", html) == "react"


def test_detector_jsonld_and_api():
    detector = Detector()
    html_jsonld = '<script type="application/ld+json">{"@context":"http://schema.org"}</script>'
    assert detector.detect("https://example.com", html_jsonld) == "jsonld"

    html_api = '<script type="application/json">{"key":"value"}</script>'
    assert detector.detect("https://example.com", html_api) == "api"


def test_resolve_engine():
    detector = Detector()
    engine = detector.resolve_engine("https://example.myshopify.com")
    assert engine.__class__.__name__ == "PlaywrightEngine"
    engine = detector.resolve_engine("https://example.com")
    assert engine.__class__.__name__ == "HtmlEngine"
