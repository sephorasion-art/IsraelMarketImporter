import pytest

from engine.models import EnginePayload


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


def test_playwright_engine_returns_extended_payload_fields(monkeypatch):
    from engine.playwright_engine import PlaywrightEngine

    def fake_scrape_payload(self, url, options=None):
        return EnginePayload(
            html="<html><body>ok</body></html>",
            title="Demo",
            final_url=url,
            network_calls=["https://example.com/api/products"],
            api_payloads=[{"products": [{"name": "Demo"}]}],
            screenshots=["/tmp/shot1.png", "/tmp/shot2.png"],
            logs=["goto=https://example.com", "analysis_ms=123"],
            elapsed_ms=123,
        )

    monkeypatch.setattr(PlaywrightEngine, "scrape_payload", fake_scrape_payload)

    result = PlaywrightEngine().scrape("https://example.com")

    assert result["html"].startswith("<html>")
    assert isinstance(result["json"], list)
    assert isinstance(result["screenshots"], list)
    assert isinstance(result["logs"], list)
    assert isinstance(result["elapsed_ms"], int)
