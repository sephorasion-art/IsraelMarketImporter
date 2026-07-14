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

        logger.info(f"Code HTTP: {payload.status_code if payload.status_code is not None else 'unknown'}")
        logger.info(f"URL finale après redirections: {payload.final_url or url}")
        logger.info(f"Titre de la page: {payload.title or '-'}")
        logger.info(f"Nombre d'éléments détectés: {payload.dom_product_elements}")

        # 1) Playwright + DOM first.
        products = self.parser.parse_products(payload.html, base_url=payload.final_url or url)
        if products:
            logger.info(f"Produits extraits depuis DOM: {len(products)}")

        # 2) Then JSON-discovered products from intercepted network responses.
        if not products:
            products = list(payload.discovered_products or [])
            if products:
                logger.info(f"Produits extraits depuis découverte réseau/API: {len(products)}")

        # 3) Then generic JSON payload parsing.
        if not products and payload.api_payloads:
            logger.info("Aucun produit direct, tentative parse_api_payloads")
            products = self.parser.parse_api_payloads(payload.api_payloads)
            if products:
                logger.info(f"Produits extraits via parse_api_payloads: {len(products)}")

        # 4) Fallback API engine.
        if not products:
            logger.info("Toujours 0 produit, fallback ApiEngine")
            api_payload = ApiEngine().scrape(url, options)
            logger.info(f"Code HTTP fallback ApiEngine: {api_payload.status_code if api_payload.status_code is not None else 'unknown'}")
            logger.info(f"URL finale fallback ApiEngine: {api_payload.final_url or url}")
            products = list(api_payload.discovered_products or [])
            if not products and api_payload.api_payloads:
                products = self.parser.parse_api_payloads(api_payload.api_payloads)
            if products:
                logger.info(f"Produits extraits via ApiEngine: {len(products)}")

        # 5) HTML last resort only.
        if not products:
            logger.info("Dernier recours: parsing HTML")
            products = self.parser.parse_products(payload.html, base_url=payload.final_url or url)

        if payload.errors:
            for err in payload.errors[:20]:
                logger.warning(f"Erreur éventuelle: {err}")

        logger.info(f"Nombre de produits extraits: {len(products)}")
        if not products:
            logger.warning("Aucun produit trouvé après toutes les méthodes d'extraction")

        if options.debug:
            logger.info(f"Debug code HTTP: {payload.status_code if payload.status_code is not None else 'unknown'}")
            logger.info(f"Debug URL appelée: {payload.final_url or url}")
            logger.info(f"Debug titre de la page: {payload.title or '-'}")
            logger.info(f"Debug nombre d'éléments détectés: {payload.dom_product_elements}")
            logger.info(f"Debug API détectées: {len(payload.api_urls)}")
            logger.info(f"Debug réponses JSON: {len(payload.api_payloads)}")
            logger.info(f"Debug produits trouvés: {len(products)}")
            logger.info(f"Debug erreurs éventuelles: {len(payload.errors)}")
            logger.info(f"Debug temps d'analyse: {payload.elapsed_ms} ms")

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