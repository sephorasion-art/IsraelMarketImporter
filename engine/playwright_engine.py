import asyncio
import os
import re
import tempfile
import threading
import time

from engine.base_engine import BaseEngine
from engine.models import EnginePayload, RuntimeOptions


class PlaywrightEngine(BaseEngine):

    def __init__(self, headless: bool = True) -> None:
        self.headless = headless

    @staticmethod
    def _log(logs: list[str], message: str) -> None:
        logs.append(message)

    async def _safe_screenshot(self, page, path: str, logs: list[str]) -> None:
        try:
            await page.screenshot(path=path, full_page=True)
            self._log(logs, f"screenshot: {path}")
        except Exception as exc:
            self._log(logs, f"screenshot_error: {exc}")

    async def _wait_for_network_idle(self, page, logs: list[str], timeout_ms: int = 12000) -> None:
        try:
            await page.wait_for_load_state("networkidle", timeout=timeout_ms)
        except Exception as exc:
            self._log(logs, f"network_idle_timeout: {exc}")

    async def _close_cookie_popups(self, page, logs: list[str]) -> int:
        clicked = 0
        text_candidates = [
            "accept",
            "accept all",
            "agree",
            "allow all",
            "continue",
            "got it",
            "ok",
            "i understand",
            "accepter",
            "tout accepter",
            "j'accepte",
            "d'accord",
            "fermer",
            "ok, understood",
            "accept cookies",
            "allow cookies",
            "voir plus",
            "הסכמה",
            "אישור",
            "קבל הכל",
        ]
        selector_candidates = [
            "#onetrust-accept-btn-handler",
            "button[aria-label*='accept' i]",
            "button[id*='accept' i]",
            "button[class*='accept' i]",
            "button[data-testid*='accept' i]",
            "button[id*='cookie' i]",
            "button[class*='cookie' i]",
            "[aria-label*='cookies' i] button",
            "[id*='cookie' i] button",
            "[class*='cookie' i] button",
            "[role='dialog'] button",
        ]

        for selector in selector_candidates:
            try:
                loc = page.locator(selector)
                count = await loc.count()
                for i in range(min(count, 4)):
                    try:
                        await loc.nth(i).click(timeout=1500)
                        clicked += 1
                    except Exception:
                        continue
            except Exception:
                continue

        for text in text_candidates:
            try:
                loc = page.get_by_text(text, exact=False)
                count = await loc.count()
                if count <= 0:
                    continue
                await loc.first.click(timeout=1500)
                clicked += 1
            except Exception:
                continue

        if clicked:
            self._log(logs, f"cookie_popups_closed={clicked}")
            await page.wait_for_timeout(700)
        return clicked

    async def _auto_scroll(self, page, logs: list[str]) -> None:
        unchanged = 0
        for _ in range(30):
            previous = await page.evaluate("Math.max(document.body.scrollHeight, document.documentElement.scrollHeight)")
            await page.evaluate("window.scrollBy(0, window.innerHeight * 0.85)")
            await page.wait_for_timeout(350)
            await self._wait_for_network_idle(page, logs, timeout_ms=3500)
            current = await page.evaluate("Math.max(document.body.scrollHeight, document.documentElement.scrollHeight)")
            if current <= previous:
                unchanged += 1
            else:
                unchanged = 0
            if unchanged >= 4:
                break
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(500)
        self._log(logs, "scroll_completed")

    async def _click_load_more(self, page, logs: list[str]) -> int:
        labels = [
            "voir plus",
            "load more",
            "load more products",
            "show all",
            "show more",
            "afficher plus",
            "plus de produits",
            "more",
            "הצג עוד",
        ]

        selectors = [
            "button[class*='load' i]",
            "a[class*='load' i]",
            "button[id*='load' i]",
            "button[class*='more' i]",
            "a[class*='more' i]",
            "[data-testid*='load' i]",
            "[data-testid*='more' i]",
        ]

        click_count = 0
        for _ in range(12):
            clicked_in_round = False
            for selector in selectors:
                try:
                    loc = page.locator(selector)
                    count = await loc.count()
                    if count <= 0:
                        continue
                    await loc.first.click(timeout=1300)
                    clicked_in_round = True
                    click_count += 1
                    self._log(logs, f"load_more_clicked_selector={selector}")
                    await page.wait_for_timeout(700)
                    await self._wait_for_network_idle(page, logs, timeout_ms=4500)
                except Exception:
                    continue

            for text in labels:
                loc = page.get_by_text(text, exact=False)
                count = await loc.count()
                if count > 0:
                    try:
                        await loc.first.click(timeout=1300)
                        clicked_in_round = True
                        click_count += 1
                        self._log(logs, f"load_more_clicked_text={text}")
                        await page.wait_for_timeout(700)
                        await self._wait_for_network_idle(page, logs, timeout_ms=4500)
                    except Exception:
                        continue

            if not clicked_in_round:
                break
        return click_count

    @staticmethod
    def _looks_like_json_api(response) -> bool:
        try:
            url = (response.url or "").lower()
            ctype = (response.headers.get("content-type") or "").lower()
            if "application/json" in ctype or "text/json" in ctype:
                return True
            if any(token in url for token in ["/api/", "graphql", ".json", "?format=json", "ajax", "search"]):
                return True
            return False
        except Exception:
            return False

    @staticmethod
    def _looks_like_json_url(url: str) -> bool:
        u = (url or "").lower()
        return any(token in u for token in ["/api/", "graphql", ".json", "?format=json", "ajax", "products", "catalog"])

    async def _scrape_async_payload(self, url: str, options: RuntimeOptions | None = None) -> EnginePayload:
        options = options or RuntimeOptions()
        from playwright.async_api import async_playwright

        started_at = time.perf_counter()
        logs: list[str] = []
        network_calls: list[str] = []
        api_payloads: list[dict | list] = []
        json_tasks: list[asyncio.Task] = []
        json_urls_seen: set[str] = set()

        screenshots_dir = tempfile.mkdtemp(prefix="playwright_engine_", dir=os.getenv("TMPDIR"))
        screenshots: list[str] = []

        async with async_playwright() as playwright:
            launch_kwargs = {"headless": self.headless}
            if options.proxy_url:
                launch_kwargs["proxy"] = {"server": options.proxy_url}
            launch_kwargs["args"] = [
                "--disable-blink-features=AutomationControlled",
                "--no-default-browser-check",
                "--disable-dev-shm-usage",
            ]
            self._log(logs, f"launching_chromium headless={self.headless}")
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
                    self._log(logs, f"cookies_injected={len(cookies)}")

            async def capture_json_response(response) -> None:
                try:
                    if len(api_payloads) >= 30:
                        return
                    if self._looks_like_json_api(response):
                        if response.url in json_urls_seen:
                            return
                        json_urls_seen.add(response.url)
                        data = await response.json()
                        if isinstance(data, (dict, list)):
                            api_payloads.append(data)
                            self._log(logs, f"json_response_captured={response.url}")
                except Exception:
                    return

            def on_request(request):
                try:
                    network_calls.append(request.url)
                except Exception:
                    return

            def on_response(response):
                try:
                    network_calls.append(response.url)
                    if len(json_tasks) < 60:
                        json_tasks.append(asyncio.create_task(capture_json_response(response)))
                except Exception:
                    return

            page.on("request", on_request)
            page.on("response", on_response)

            self._log(logs, f"goto={url}")
            await page.goto(url, wait_until="domcontentloaded", timeout=90000)
            await self._wait_for_network_idle(page, logs, timeout_ms=15000)

            shot = os.path.join(screenshots_dir, "stage_01_loaded.png")
            await self._safe_screenshot(page, shot, logs)
            screenshots.append(shot)

            await self._close_cookie_popups(page, logs)
            shot = os.path.join(screenshots_dir, "stage_02_after_cookies.png")
            await self._safe_screenshot(page, shot, logs)
            screenshots.append(shot)

            await self._auto_scroll(page, logs)
            load_more_clicks = await self._click_load_more(page, logs)
            self._log(logs, f"load_more_clicks={load_more_clicks}")
            await self._wait_for_network_idle(page, logs, timeout_ms=12000)

            shot = os.path.join(screenshots_dir, "stage_03_final.png")
            await self._safe_screenshot(page, shot, logs)
            screenshots.append(shot)

            if json_tasks:
                await asyncio.gather(*json_tasks, return_exceptions=True)

            # Pull a limited set of JSON responses to feed parser fallbacks.
            for req_url in network_calls:
                if len(api_payloads) >= 10:
                    break
                try:
                    if self._looks_like_json_url(req_url) and req_url not in json_urls_seen:
                        resp = await page.request.get(req_url, timeout=5000)
                        ctype = (resp.headers.get("content-type") or "").lower()
                        if "json" in ctype:
                            api_payloads.append(await resp.json())
                            json_urls_seen.add(req_url)
                            self._log(logs, f"json_replayed_from_request={req_url}")
                except Exception:
                    continue

            title = await page.title()
            html = await page.content()
            final_url = page.url
            elapsed_ms = int((time.perf_counter() - started_at) * 1000)
            self._log(logs, f"analysis_ms={elapsed_ms}")

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
                screenshots=screenshots,
                logs=logs,
                elapsed_ms=elapsed_ms,
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
            "json": payload.api_payloads,
            "network_calls": payload.network_calls,
            "api_payloads": payload.api_payloads,
            "final_url": payload.final_url,
            "screenshots": payload.screenshots,
            "logs": payload.logs,
            "elapsed_ms": payload.elapsed_ms,
        }

    def get_html(self, url: str, options: RuntimeOptions | None = None) -> str:
        """Load the page and return only the HTML content for compatibility."""
        result = self.scrape_payload(url, options)
        return result.html
