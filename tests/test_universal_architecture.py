from engine.detector import Detector
from engine.api_engine import ApiEngine
from engine.models import EnginePayload
from engine.parser import ImportPipeline
from engine.playwright_engine import PlaywrightEngine
from engine.universal_parser import UniversalParser


def test_detector_detects_prestashop_bigcommerce_graphql_and_schema():
    detector = Detector()

    html_presta = '<html><script>var prestashop = {};</script></html>'
    report_presta = detector.analyze("https://shop.example.com", html_presta)
    assert report_presta.cms == "prestashop"

    html_big = '<html><script src="https://cdn11.bigcommerce.com/some.js"></script></html>'
    report_big = detector.analyze("https://store.example.com", html_big)
    assert report_big.cms == "bigcommerce"

    html_graphql = '<html><script>fetch("/graphql");</script></html>'
    report_graphql = detector.analyze("https://api.example.com", html_graphql)
    assert report_graphql.has_graphql is True

    html_schema = '<div itemscope itemtype="https://schema.org/Product"><span itemprop="name">Demo</span></div>'
    report_schema = detector.analyze("https://example.com", html_schema)
    assert report_schema.has_schema_microdata is True


def test_universal_parser_schema_microdata_extraction():
    html = '''
    <div itemscope itemtype="https://schema.org/Product">
      <span itemprop="name">Micro Product</span>
      <span itemprop="description">Micro Description</span>
      <span itemprop="sku">ABC-1</span>
      <span itemprop="price" content="39.90"></span>
      <img itemprop="image" src="/img/p.jpg" />
      <a href="/p/micro">voir</a>
    </div>
    '''
    parser = UniversalParser()
    products = parser.parse(html, base_url="https://example.com")
    assert len(products) == 1
    p = products[0]
    assert p["title"] == "Micro Product"
    assert p["price"] == 39.9
    assert p["images"] == ["https://example.com/img/p.jpg"]


def test_import_pipeline_orchestrates_detection_engine_and_parser(monkeypatch):
    def fake_pw_payload(self, url: str, options=None):
        return EnginePayload(
            html="<html><body><div>dynamic page</div></body></html>",
            final_url=url,
            api_urls=[f"{url}/api/products"],
            api_payloads=[{"items": [{"name": "Demo", "price": "10.00", "id": "p1"}]}],
        )

    monkeypatch.setattr(PlaywrightEngine, "scrape_payload", fake_pw_payload)

    pipeline = ImportPipeline()

    result = pipeline.run("https://example.com/category")
    assert result.engine_used == "PlaywrightEngine"
    assert result.elapsed_ms >= 0
    assert isinstance(result.products, list)
    assert len(result.logs) >= 1


def test_import_pipeline_uses_html_as_last_resort(monkeypatch):
    def fake_pw_payload(self, url: str, options=None):
        return EnginePayload(
            html='<div class="product-card"><h2>PW Product</h2><span class="price">19.90</span></div>',
            final_url=url,
            api_payloads=[],
            discovered_products=[],
        )

    def fake_api_scrape(self, url: str, options=None):
        return EnginePayload(html="", final_url=url, api_payloads=[], discovered_products=[])

    monkeypatch.setattr(PlaywrightEngine, "scrape_payload", fake_pw_payload)
    monkeypatch.setattr(ApiEngine, "scrape", fake_api_scrape)

    pipeline = ImportPipeline()
    result = pipeline.run("https://example.com/category")
    assert len(result.products) >= 1
