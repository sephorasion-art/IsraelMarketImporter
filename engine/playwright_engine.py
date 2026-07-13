from playwright.sync_api import sync_playwright


class PlaywrightEngine:

    def scrape(self, url):

        with sync_playwright() as p:

            browser = p.chromium.launch(
                headless=True
            )

            page = browser.new_page()

            page.goto(
                url,
                wait_until="networkidle",
                timeout=60000
            )

            title = page.title()

            html = page.content()

            browser.close()

            return {
                "title": title,
                "html": html
            }