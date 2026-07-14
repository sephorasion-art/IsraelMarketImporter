from __future__ import annotations


class NetworkAnalyzer:
    """Analyze observed network calls to infer API capabilities."""

    def has_rest(self, calls: list[str]) -> bool:
        for call in calls or []:
            lower = call.lower()
            if "/api/" in lower or "wp-json" in lower or "/rest/" in lower:
                return True
        return False

    def has_graphql(self, calls: list[str]) -> bool:
        return any("graphql" in (call or "").lower() for call in (calls or []))

    def has_json_endpoints(self, calls: list[str]) -> bool:
        for call in calls or []:
            lower = call.lower()
            if lower.endswith(".json") or "format=json" in lower:
                return True
        return False
