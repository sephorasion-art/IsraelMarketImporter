from engine.api_detector import ApiDetector
from engine.cms_detector import CmsDetector
from engine.detector import Detector
from engine.engine_selector import EngineSelector
from engine.technology_detector import TechnologyDetector


def test_technology_detector_covers_modern_frameworks():
    detector = TechnologyDetector()
    html = """
    <script>window.__NEXT_DATA__={};window.__INITIAL_STATE__={};</script>
    <div data-reactroot></div>
    <script src="/_nuxt/app.js"></script>
    <script src="/_astro/app.js"></script>
    <div x-data="{}"></div>
    <div ng-version="17.0.0"></div>
    <div data-v-1234></div>
    """
    technologies = detector.detect("https://example.com", html)
    assert "html" in technologies
    assert "react" in technologies
    assert "nextjs" in technologies
    assert "nuxt" in technologies
    assert "astro" in technologies
    assert "alpine" in technologies
    assert "angular" in technologies
    assert "vue" in technologies


def test_cms_detector_covers_requested_platforms():
    detector = CmsDetector()
    assert detector.detect("https://store.myshopify.com", "") == "shopify"
    assert detector.detect("https://example.com", "wp-content/plugins/woocommerce") == "woocommerce"
    assert detector.detect("https://example.com", "Magento.config") == "magento"
    assert detector.detect("https://example.com", "var prestashop = {}") == "prestashop"
    assert detector.detect("https://example.com", "cdn11.bigcommerce.com") == "bigcommerce"
    assert detector.detect("https://example.com", "WixLoader") == "wix"
    assert detector.detect("https://example.com", "index.php?route=product/product") == "opencart"
    assert detector.detect("https://example.com", "static.squarespace.com") == "squarespace"


def test_api_detector_covers_rest_graphql_json_jsonld_and_hydration():
    detector = ApiDetector()
    html = """
    <script id="__NEXT_DATA__" type="application/json">{"props":{}}</script>
    <script>window.__INITIAL_STATE__={}; fetch('/graphql'); fetch('/api/products');</script>
    <script type="application/ld+json">{"@type":"Product"}</script>
    """
    signals = detector.analyze(html, headers={"content-type": "text/html"}, network_calls=["https://example.com/graphql"])
    assert signals.has_rest is True
    assert signals.has_graphql is True
    assert signals.has_json is True
    assert signals.has_jsonld is True
    assert signals.has_hydration_data is True
    assert signals.has_next_data is True
    assert signals.has_initial_state is True


def test_engine_selector_picks_best_engine():
    selector = EngineSelector()
    api_detector = ApiDetector()

    api_signals = api_detector.analyze("<script>fetch('/graphql')</script>")
    assert selector.select("unknown", ["html"], api_signals) == "api"

    dynamic_signals = api_detector.analyze("<div data-reactroot></div>")
    assert selector.select("shopify", ["react", "html"], dynamic_signals) == "playwright"

    html_signals = api_detector.analyze("<html><body>simple catalog</body></html>")
    assert selector.select("unknown", ["html"], html_signals) == "html"


def test_detector_modular_chain_outputs_expected_report_and_engine():
    detector = Detector()
    html = '<script>window.__NEXT_DATA__={}; fetch("/api/products");</script>'
    report = detector.analyze("https://example.com", html)
    assert report.is_nextjs is True
    assert report.has_rest_api is True
    assert report.preferred_engine in {"api", "playwright"}

    engine = detector.resolve_engine("https://example.com", html)
    assert engine.__class__.__name__ in {"ApiEngine", "PlaywrightEngine", "HtmlEngine"}
