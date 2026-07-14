import asyncio
import threading

from engine.base_engine import BaseEngine
from engine.models import EnginePayload, RuntimeOptions


class PlaywrightEngine(BaseEngine):

    def __init__(self, headless: bool = True) -> None:
        self.headless = headless

    async def _auto_scroll(self, page) -> None:
        for _ in range(8):
            previous = await page.evaluate("document.body.scrollHeight")
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(500)
            current = await page.evaluate("document.body.scrollHeight")
            if current == previous:
                break

    async def _click_load_more(self, page) -> None:
        labels = [
            "voir plus",
            "load more",
            "show more",
            "more",
            "הצג עוד",
        ]
        for text in labels:
            loc = page.get_by_text(text, exact=False)
            count = await loc.count()
            if count > 0:
                try:
                    await loc.first.click(timeout=1200)
                    await page.wait_for_timeout(600)
                except Exception:
                    continue

    async def _scrape_async_payload(self, url: str, options: RuntimeOptions | None = None) -> EnginePayload:
        options = options or RuntimeOptions()
        from playwright.async_api import async_playwright

        network_calls: list[str] = []
        api_payloads: list[dict | list] = []
        json_tasks: list[asyncio.Task] = []

        async with async_playwright() as playwright:
            launch_kwargs = {"headless": self.headless}
            if options.proxy_url:
                launch_kwargs["proxy"] = {"server": options.proxy_url}
            browser = await playwright.chromium.launch(**launch_kwargs)
            page = await browser.new_page(
                viewport={"width": 1400, "height": 900},
                user_agent=(
                    options.user_agent or
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
                ),
                locale="en-US",
            )
            await page.set_extra_http_headers(
                {
                    "Accept-Language": "en-US,en;q=0.9,fr;q=0.8",
                    "Upgrade-Insecure-Requests": "1",
                }
            )

            if options.cookie_header:
                cookies = []
                host = ""
                try:
                    host = url.split("/")[2]
                except Exception:
                    host = ""
                for kv in options.cookie_header.split(";"):
                    kv = kv.strip()
                    if not kv or "=" not in kv:
                        continue
                    name, value = kv.split("=", 1)
                    cookies.append(
                        {
                            "name": name.strip(),
                            "value": value.strip(),
                            "domain": f".{host}" if host else host,
                            "path": "/",
                        }
                    )
                if cookies:
                    await page.context.add_cookies(cookies)

            async def capture_json_response(response) -> None:
                try:
                    ctype = (response.headers.get("content-type") or "").lower()
                    u = response.url.lower()
                    if len(api_payloads) >= 30:
                        return
                    if "json" in ctype or "graphql" in u or "/api/" in u:
                        data = await response.json()
                        if isinstance(data, (dict, list)):
                            api_payloads.append(data)
                except Exception:
                    return

            def on_response(response):
                try:
                    network_calls.append(response.url)
                    if len(json_tasks) < 60:
                        json_tasks.append(asyncio.create_task(capture_json_response(response)))
                except Exception:
                    return

            page.on("response", on_response)

            await page.goto(url, wait_until="networkidle", timeout=60000)
            await self._auto_scroll(page)
            await self._click_load_more(page)
            await page.wait_for_load_state("networkidle")

            if json_tasks:
                await asyncio.gather(*json_tasks, return_exceptions=True)

            # Pull a limited set of JSON responses to feed parser fallbacks.
            for req_url in network_calls:
                if len(api_payloads) >= 10:
                    break
                try:
                    if "graphql" in req_url.lower() or "/api/" in req_url.lower() or "products" in req_url.lower():
                        resp = await page.request.get(req_url, timeout=5000)
                        ctype = (resp.headers.get("content-type") or "").lower()
                        if "json" in ctype:
                            api_payloads.append(await resp.json())
                except Exception:
                    continue

            title = await page.title()
            html = await page.content()
            final_url = page.url
            await page.close()
            await browser.close()
            return EnginePayload(
                html=html,
                title=title or "",
                status_code=200,
                final_url=final_url,
                response_headers={},
                network_calls=network_calls,
                api_payloads=api_payloads,
            )

    def _run_async(self, coro_func, *args, **kwargs):
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro_func(*args, **kwargs))

        result = {}
        def run_in_thread():
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            result["value"] = new_loop.run_until_complete(coro_func(*args, **kwargs))
            new_loop.close()

        thread = threading.Thread(target=run_in_thread)
        thread.start()
        thread.join()
        return result["value"]

    def scrape_payload(self, url: str, options: RuntimeOptions | None = None) -> EnginePayload:
        """Typed payload API for new architecture."""
        return self._run_async(self._scrape_async_payload, url, options)

    def scrape(self, url: str, options: RuntimeOptions | None = None) -> dict:
        """Backward-compatible API returning a dict for legacy tests/callers."""
        payload = self.scrape_payload(url, options)
        return {
            "title": payload.title,
            "html": payload.html,
            "network_calls": payload.network_calls,
            "api_payloads": payload.api_payloads,
            "final_url": payload.final_url,
        }

    def get_html(self, url: str, options: RuntimeOptions | None = None) -> str:
        """Load the page and return only the HTML content for compatibility."""
        result = self.scrape_payload(url, options)
        return result.html
