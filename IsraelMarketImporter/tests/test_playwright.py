import pytest


def test_playwright_engine_smoke():
    # Skip if Playwright or the engine is not available in this environment
    pytest.importorskip("playwright")
    try:
        from engine.playwright_engine import PlaywrightEngine
    except Exception:
        pytest.skip("Playwright engine not importable")

    engine = PlaywrightEngine()
    result = engine.scrape("https://example.com")
    assert isinstance(result, dict)
    assert "html" in result and "title" in result
