from __future__ import annotations

import json

import requests

from engine.base_engine import BaseEngine
from engine.models import EnginePayload, RuntimeOptions


class ApiEngine(BaseEngine):
	"""Engine for endpoints or pages where product data is available as JSON."""

	def scrape(self, url: str, options: RuntimeOptions | None = None) -> EnginePayload:
		options = options or RuntimeOptions()
		headers = {
			"User-Agent": options.user_agent or "Mozilla/5.0",
			"Accept": "application/json,text/html,*/*",
		}
		if options.cookie_header:
			headers["Cookie"] = options.cookie_header

		proxies = None
		if options.proxy_url:
			proxies = {"http": options.proxy_url, "https": options.proxy_url}

		response = requests.get(url, headers=headers, timeout=30, proxies=proxies)
		response.raise_for_status()

		body = response.text
		api_payloads = []
		ctype = (response.headers.get("content-type") or "").lower()

		if "application/json" in ctype:
			try:
				api_payloads.append(response.json())
			except ValueError:
				pass
		else:
			try:
				api_payloads.append(json.loads(body))
			except Exception:
				pass

		return EnginePayload(
			html=body,
			title="",
			status_code=response.status_code,
			final_url=str(response.url),
			response_headers=dict(response.headers),
			network_calls=[url],
			api_payloads=api_payloads,
		)
