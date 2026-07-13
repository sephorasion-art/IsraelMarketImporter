from bs4 import BeautifulSoup
from models.product import Product


class UniversalParser:

    def parse(self, html):

        soup = BeautifulSoup(html, "lxml")

        products = []

        # Sélecteurs les plus courants
        selectors = [
            ".product",
            ".product-item",
            ".product-card",
            ".item",
            ".card",
            "[data-product]",
            "article"
        ]

        cards = []

        for selector in selectors:
            cards = soup.select(selector)
            if cards:
                print(f"Sélecteur trouvé : {selector}")
                break

        for card in cards:

            product = Product()

            # ---------- TITRE ----------
            title = (
                card.select_one("h1") or
                card.select_one("h2") or
                card.select_one("h3") or
                card.select_one(".title") or
                card.select_one(".product-title")
            )

            if title:
                product.title = title.get_text(strip=True)

            # ---------- PRIX ----------
            price = (
                card.select_one(".price") or
                card.select_one(".product-price")
            )

            if price:
                product.price = price.get_text(strip=True)

            # ---------- IMAGE ----------
            img = card.select_one("img")

            if img:
                product.image = img.get("src", "")

            # ---------- URL ----------
            link = card.select_one("a")

            if link:
                product.url = link.get("href", "")

            products.append(product)

        return products