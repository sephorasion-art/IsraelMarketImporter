from __future__ import annotations

import time

from engine.detector import Detector
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

        # API-first strategy for modern sites: Playwright interception before HTML parsing.
        engine = PlaywrightEngine(debug=options.debug)
        logger.info(f"Moteur choisi: {engine.__class__.__name__}")
        payload = engine.scrape_payload(url, options)

        report = self.detector.analyze(url, payload.html, payload.response_headers)
        logger.info(f"CMS détecté: {report.cms}")
        logger.info(f"Technologies: {', '.join(report.technologies)}")

        products = list(payload.discovered_products or [])
        if products:
            logger.info(f"Produits détectés depuis réseau/API: {len(products)}")
        elif payload.api_payloads:
            logger.info("Aucun produit direct dans les réponses JSON, tentative parse_api_payloads")
            products = self.parser.parse_api_payloads(payload.api_payloads)

        lower_html = (payload.html or "").lower()
        blocked = any(token in lower_html for token in ["<title>403", "captcha", "access denied", "forbidden"])
        if blocked:
            logger.warning(
                "La page semble protégée (403/captcha). "
                "Extraction limitée dans cet environnement."
            )

        if not products:
            logger.info("Toujours 0 produit, fallback ApiEngine")
            api_payload = ApiEngine().scrape(url, options)
            if api_payload.api_payloads:
                products = self.parser.parse_api_payloads(api_payload.api_payloads)

        if not products:
            logger.info("Fallback final: parsing HTML (dernier recours)")
            products = self.parser.parse_products(payload.html, base_url=payload.final_url or url)

        if options.debug:
            logger.info(f"Debug URL appelée: {payload.final_url or url}")
            logger.info(f"Debug API détectées: {len(payload.api_urls)}")
            logger.info(f"Debug réponses JSON: {len(payload.api_payloads)}")
            logger.info(f"Debug produits trouvés: {len(products)}")
            logger.info(f"Debug temps moteur: {payload.elapsed_ms} ms")

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