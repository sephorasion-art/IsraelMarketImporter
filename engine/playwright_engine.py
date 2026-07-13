from playwright.sync_api import sync_playwright


class PlaywrightEngine:

    def get_html(self, url):

        with sync_playwright() as p:

            browser = p.chromium.launch(headless=True)

            page = browser.new_page()

            page.goto(
                url,
                wait_until="networkidle",
                timeout=60000
            )

            page.mouse.wheel(0, 15000)

            page.wait_for_timeout(3000)

            html = page.content()

            browser.close()

            return html