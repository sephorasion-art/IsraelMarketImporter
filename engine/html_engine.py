import requests

from engine.base_engine import BaseEngine
from engine.models import EnginePayload, RuntimeOptions


class HtmlEngine(BaseEngine):

    def scrape(self, url: str, options: RuntimeOptions | None = None) -> EnginePayload:
        options = options or RuntimeOptions()

        headers = {"User-Agent": options.user_agent or "Mozilla/5.0"}

        if options.cookie_header:
            headers["Cookie"] = options.cookie_header

        proxies = None
        if options.proxy_url:
            proxies = {"http": options.proxy_url, "https": options.proxy_url}

        response = requests.get(url, headers=headers, timeout=30, proxies=proxies)

        response.raise_for_status()

        return EnginePayload(
            html=response.text,
            title="",
            status_code=response.status_code,
            final_url=str(response.url),
            response_headers=dict(response.headers),
            network_calls=[],
            api_payloads=[],
        )