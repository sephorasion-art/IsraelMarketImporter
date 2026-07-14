from __future__ import annotations

import re
from dataclasses import dataclass

from engine.graphql_detector import GraphqlDetector
from engine.jsonld_detector import JsonLdDetector
from engine.network_analyzer import NetworkAnalyzer


@dataclass(slots=True)
class ApiSignals:
    has_rest: bool = False
    has_graphql: bool = False
    has_json: bool = False
    has_jsonld: bool = False
    has_hydration_data: bool = False
    has_next_data: bool = False
    has_initial_state: bool = False


class ApiDetector:
    """Detect API-oriented extraction opportunities from HTML and headers."""

    _REST_PATTERN = re.compile(r"/api/|wp-json|rest/v\d+", re.IGNORECASE)
    _JSON_SCRIPT_PATTERN = re.compile(r"<script[^>]+type=['\"]application/json['\"][^>]*>", re.IGNORECASE)
    _HYDRATION_PATTERN = re.compile(
        r"__NEXT_DATA__|__INITIAL_STATE__|__APOLLO_STATE__|window\.__NUXT__|hydration",
        re.IGNORECASE,
    )

    def __init__(self) -> None:
        self._jsonld = JsonLdDetector()
        self._graphql = GraphqlDetector()
        self._network = NetworkAnalyzer()

    def analyze(
        self,
        html: str,
        headers: dict[str, str] | None = None,
        network_calls: list[str] | None = None,
    ) -> ApiSignals:
        headers = headers or {}
        network_calls = network_calls or []
        ctype = (headers.get("content-type") or "").lower()

        has_json = "application/json" in ctype or bool(self._JSON_SCRIPT_PATTERN.search(html or ""))
        has_rest = bool(self._REST_PATTERN.search(html or "")) or self._network.has_rest(network_calls)
        has_graphql = self._graphql.has_graphql(html or "", network_calls)
        has_jsonld = self._jsonld.has_jsonld(html or "")

        body = html or ""
        has_next_data = "__NEXT_DATA__" in body
        has_initial_state = "__INITIAL_STATE__" in body
        has_hydration = bool(self._HYDRATION_PATTERN.search(body))

        return ApiSignals(
            has_rest=has_rest,
            has_graphql=has_graphql,
            has_json=has_json,
            has_jsonld=has_jsonld,
            has_hydration_data=has_hydration,
            has_next_data=has_next_data,
            has_initial_state=has_initial_state,
        )
