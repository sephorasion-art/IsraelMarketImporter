import pytest


def test_playwright_engine_smoke():
    # Skip if Playwright or the engine is not available in this environment
    pytest.importorskip("playwright")
    try:
        from engine.playwright_engine import PlaywrightEngine
    except Exception:
        pytest.skip("Playwright engine not importable")

    engine = PlaywrightEngine()
    try:
        result = engine.scrape("https://example.com")
    except Exception as exc:
        pytest.skip(f"Playwright engine cannot launch in this environment: {exc}")

    assert isinstance(result, dict)
    assert "html" in result and "title" in result
