from __future__ import annotations

import time

from engine.detector import Detector
from engine.html_engine import HtmlEngine
from engine.logger import ImportLogger
from engine.models import ImportResult, RuntimeOptions
from engine.playwright_engine import PlaywrightEngine
from engine.api_engine import ApiEngine
from engine.universal_parser import UniversalParser as DictUniversalParser


class ImportPipeline:
    """Universal import orchestration: URL -> detection -> best engine -> parse."""

    def __init__(self, detector: Detector | None = None, parser: DictUniversalParser | None = None) -> None:
        self.detector = detector or Detector()
        self.parser = parser or DictUniversalParser()

    def run(self, url: str, options: RuntimeOptions | None = None) -> ImportResult:
        options = options or RuntimeOptions()
        logger = ImportLogger("import.pipeline")
        start = time.perf_counter()

        logger.info(f"URL reçue: {url}")

        # quick probe with HTML engine to bootstrap detection
        probe = HtmlEngine().scrape(url, options)
        report = self.detector.analyze(url, probe.html, probe.response_headers)
        logger.info(f"CMS détecté: {report.cms}")
        logger.info(f"Technologies: {', '.join(report.technologies)}")

        engine = self.detector.resolve_engine(url, probe.html)
        logger.info(f"Moteur choisi: {engine.__class__.__name__}")

        if hasattr(engine, "scrape_payload"):
            payload = engine.scrape_payload(url, options)
        else:
            payload = engine.scrape(url, options)
        products = self.parser.parse_products(payload.html, base_url=payload.final_url or url)

        lower_html = (payload.html or "").lower()
        blocked = any(token in lower_html for token in ["<title>403", "captcha", "access denied", "forbidden"])
        if blocked:
            logger.warning(
                "La page semble protégée (403/captcha). "
                "Extraction limitée dans cet environnement."
            )

        # fallback from intercepted API payloads when DOM extraction is weak
        if not products and payload.api_payloads:
            logger.info("Aucun produit DOM, tentative via payloads API")
            products = self.parser.parse_api_payloads(payload.api_payloads)

        # If API extraction returns too few items, try Playwright and keep best.
        if isinstance(engine, ApiEngine) and len(products) <= 1:
            logger.info("Extraction API faible (<=1), tentative Playwright pour enrichir")
            try:
                pw_payload = PlaywrightEngine().scrape_payload(url, options)
                pw_products = self.parser.parse_products(pw_payload.html, base_url=pw_payload.final_url or url)
                if not pw_products and pw_payload.api_payloads:
                    pw_products = self.parser.parse_api_payloads(pw_payload.api_payloads)
                if len(pw_products) > len(products):
                    products = pw_products
            except Exception as exc:
                logger.warning(f"Fallback Playwright ignoré: {exc}")

        # Robust fallback chain for dynamic stores: try Playwright, then API.
        if not products and not isinstance(engine, PlaywrightEngine):
            logger.info("Aucun produit trouvé, fallback Playwright")
            pw_engine = PlaywrightEngine()
            pw_payload = pw_engine.scrape_payload(url, options)
            lower_pw = (pw_payload.html or "").lower()
            if any(token in lower_pw for token in ["<title>403", "captcha", "access denied", "forbidden"]):
                logger.warning("Fallback Playwright bloqué par protection anti-bot (403/captcha)")
            products = self.parser.parse_products(pw_payload.html, base_url=pw_payload.final_url or url)
            if not products and pw_payload.api_payloads:
                logger.info("Fallback Playwright sans DOM produit, tentative payloads API")
                products = self.parser.parse_api_payloads(pw_payload.api_payloads)

        if not products and not isinstance(engine, ApiEngine):
            logger.info("Toujours 0 produit, fallback ApiEngine")
            api_payload = ApiEngine().scrape(url, options)
            if api_payload.api_payloads:
                products = self.parser.parse_api_payloads(api_payload.api_payloads)

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        logger.info(f"Import terminé en {elapsed_ms} ms, {len(products)} produit(s)")

        return ImportResult(
            detection=report,
            engine_used=engine.__class__.__name__,
            elapsed_ms=elapsed_ms,
            products=products,
            logs=logger.entries,
        )


class UniversalParser(DictUniversalParser):
    """Backward-compatible parser that returns Product models on .parse()."""

    def parse(self, html: str, base_url: str = ""):
        items = super().parse(html, base_url)
        products = []
        for item in items:
            images = item.get("images") or []
            image = images[0] if images else ""
            products.append(
                {
                    "title": item.get("title") or "",
                    "description": item.get("description") or "",
                    "price": item.get("price"),
                    "compare_at_price": item.get("compare_at_price"),
                    "sku": item.get("sku") or "",
                    "barcode": item.get("barcode") or "",
                    "brand": item.get("brand") or "",
                    "category": item.get("category") or "",
                    "image": image,
                    "gallery": images,
                    "stock": item.get("stock"),
                    "weight": item.get("weight"),
                    "tags": item.get("tags") or [],
                    "url": item.get("url") or "",
                }
            )
        # Keep legacy contract: objects with attributes (title, price, image, url)
        class _P:
            def __init__(self, data):
                self.__dict__.update(data)

        return [_P(p) for p in products]