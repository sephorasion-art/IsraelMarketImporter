from urllib.parse import urlparse

from engine.api_engine import ApiEngine
from engine.api_detector import ApiDetector
from engine.cms_detector import CmsDetector
from engine.engine_selector import EngineSelector
from engine.html_engine import HtmlEngine
from engine.jsonld_detector import JsonLdDetector
from engine.models import DetectionReport
from engine.playwright_engine import PlaywrightEngine
from engine.schema_detector import SchemaDetector
from engine.technology_detector import TechnologyDetector


class Detector:

    def __init__(self) -> None:
        self.technology_detector = TechnologyDetector()
        self.cms_detector = CmsDetector()
        self.api_detector = ApiDetector()
        self.schema_detector = SchemaDetector()
        self.jsonld_detector = JsonLdDetector()
        self.engine_selector = EngineSelector()

    def analyze(self, url: str, html: str | None = None, headers: dict[str, str] | None = None) -> DetectionReport:
        host = urlparse(url).netloc.lower()
        body = html or ""
        headers = headers or {}

        cms = self.cms_detector.detect(url, body)
        technologies = self.technology_detector.detect(url, body)
        api = self.api_detector.analyze(body, headers=headers)

        has_schema = self.schema_detector.has_schema_microdata(body)
        has_jsonld = self.jsonld_detector.has_jsonld(body)
        if has_schema:
            technologies.append("schema.org")
        if has_jsonld:
            technologies.append("json-ld")
        if api.has_graphql:
            technologies.append("graphql")
        if api.has_rest:
            technologies.append("rest-api")
        if api.has_json:
            technologies.append("embedded-json")

        preferred_engine = self.engine_selector.select(cms=cms, technologies=technologies, api=api)

        is_next = "nextjs" in technologies
        is_react = "react" in technologies

        return DetectionReport(
            domain=host,
            cms=cms,
            technologies=sorted(set(technologies)),
            is_html=bool(body),
            is_react=is_react,
            is_nextjs=is_next,
            has_rest_api=api.has_rest,
            has_graphql=api.has_graphql,
            has_json_api=api.has_json,
            has_jsonld=has_jsonld,
            has_schema_microdata=has_schema,
            has_hydration_data=api.has_hydration_data,
            has_next_data=api.has_next_data,
            has_initial_state=api.has_initial_state,
            preferred_engine=preferred_engine,
        )

    def detect(self, url: str, html: str | None = None) -> str:
        report = self.analyze(url, html)
        if report.cms == "shopify":
            return "shopify"
        if report.cms == "woocommerce":
            return "woocommerce"
        if report.cms == "magento":
            return "magento"
        if report.cms == "wix":
            return "wix"
        if report.cms == "prestashop":
            return "prestashop"
        if report.cms == "bigcommerce":
            return "bigcommerce"
        if self._is_tavliney(report.domain, html or ""):
            return "playwright"
        if report.is_nextjs:
            return "nextjs"
        if report.is_react:
            return "react"
        if report.has_jsonld:
            return "jsonld"
        if report.has_rest_api or report.has_graphql or self._has_api_json(html or ""):
            return "api"

        return "html"

    def resolve_engine(self, url: str, html: str | None = None):
        report = self.analyze(url, html)
        if report.preferred_engine == "api":
            return ApiEngine()
        if report.preferred_engine == "playwright":
            return PlaywrightEngine()
        return HtmlEngine()

    def _is_tavliney(self, host: str, body: str) -> bool:
        return any(domain in host for domain in [
            "tavlineypereg.co.il",
            "deli.yango.com",
            "yango.com"
        ])

    def _has_api_json(self, body: str) -> bool:
        return self.api_detector.analyze(body).has_json
