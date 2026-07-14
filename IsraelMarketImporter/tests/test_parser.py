import pytest


def test_parser_playwright_smoke():
    pytest.importorskip("playwright")
    from engine.playwright_engine import PlaywrightEngine
    from engine.parser import UniversalParser

    url = "https://deli.yango.com/en-il/catalog/grocery/category/snacks"
    engine = PlaywrightEngine()

    try:
        html = engine.get_html(url)
    except Exception as exc:
        pytest.skip(f"Playwright/network unavailable in this environment: {exc}")

    parser = UniversalParser()
    products = parser.parse(html)
    assert isinstance(products, list)