from __future__ import annotations

from engine.api_detector import ApiSignals


class EngineSelector:
    """Choose the optimal extraction engine using analyzed signals."""

    _DYNAMIC_TECH = {"react", "nextjs", "vue", "angular", "alpine", "astro", "nuxt"}
    _CMS_DYNAMIC = {"shopify", "woocommerce", "magento", "wix", "prestashop", "bigcommerce", "opencart", "squarespace"}

    def select(self, cms: str, technologies: list[str], api: ApiSignals) -> str:
        technology_set = set(technologies or [])

        if api.has_graphql or api.has_rest:
            return "api"

        if cms in self._CMS_DYNAMIC:
            return "playwright"

        if technology_set.intersection(self._DYNAMIC_TECH):
            return "playwright"

        if api.has_hydration_data or api.has_next_data or api.has_initial_state:
            return "playwright"

        return "html"
