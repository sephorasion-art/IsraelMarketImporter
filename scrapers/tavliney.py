import re
import json
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

# Tavliney base URL used to resolve relative links
BASE_URL = "https://www.tavlineypereg.co.il"
ILS_TO_EUR = 0.25


def _clean_text(value: str | None) -> str:
    if not value:
        return ""
    text = re.sub(r"\s+", " ", value)
    return text.strip()


def _parse_price(text: str | None) -> float | None:
    if not text:
        return None
    candidate_match = re.search(r"-?\d[\d\s,\.]*", text)
    if not candidate_match:
        return None

    cleaned = candidate_match.group(0).strip()
    cleaned = cleaned.replace(" ", "")

    # Normalize separators for both "1,234.56" and "1.234,56" formats.
    if "," in cleaned and "." in cleaned:
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "")
            cleaned = cleaned.replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
        parts = cleaned.split(",")
        if len(parts) == 2 and len(parts[1]) == 3:
            cleaned = "".join(parts)
        else:
            cleaned = cleaned.replace(",", ".")

    cleaned = re.sub(r"[^-0-9\.]+", "", cleaned)
    try:
        return float(cleaned)
    except ValueError:
        return None


def _price_eur_from_nis(price_nis: float | None) -> float | None:
    if price_nis is None:
        return None
    return round(price_nis * ILS_TO_EUR, 2)


def _extract_price_from_jsonld(soup: BeautifulSoup) -> float | None:
    for script in soup.find_all("script", type=lambda t: t and "application/ld+json" in t):
        try:
            payload = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue

        candidates = []
        if isinstance(payload, list):
            candidates = payload
        elif isinstance(payload, dict) and isinstance(payload.get("@graph"), list):
            candidates = payload["@graph"]
        elif isinstance(payload, dict):
            candidates = [payload]

        for item in candidates:
            if not isinstance(item, dict):
                continue
            offers = item.get("offers")
            if isinstance(offers, dict):
                price = _parse_price(str(offers.get("price") or ""))
                if price is not None:
                    return price
            direct = _parse_price(str(item.get("price") or ""))
            if direct is not None:
                return direct

    return None


def _extract_price_from_soup(soup: BeautifulSoup) -> float | None:
    selectors = [
        ".price",
        ".product-price",
        ".amount",
        ".price-value",
        "[itemprop='price']",
        "[data-price]",
        "meta[property='product:price:amount']",
        "meta[itemprop='price']",
    ]

    for selector in selectors:
        for tag in soup.select(selector):
            raw = (
                tag.get("content") or
                tag.get("data-price") or
                tag.get("value") or
                tag.get_text(strip=True)
            )
            price = _parse_price(raw)
            if price is not None:
                return price

    body_text = soup.get_text(" ", strip=True)
    for pattern in [
        r"₪\s*([0-9][0-9\.,\s]*)",
        r"([0-9][0-9\.,\s]*)\s*₪",
        r"EUR\s*([0-9][0-9\.,\s]*)",
        r"([0-9][0-9\.,\s]*)\s*EUR",
    ]:
        match = re.search(pattern, body_text, re.IGNORECASE)
        if match:
            price = _parse_price(match.group(1))
            if price is not None:
                return price

    return _extract_price_from_jsonld(soup)


def _extract_images(soup: BeautifulSoup, base_url: str) -> list[str]:
    images = []
    selectors = [
        ".product-gallery img",
        ".product-images img",
        "meta[property='og:image']",
        "img"
    ]

    for selector in selectors:
        for element in soup.select(selector):
            if selector.startswith("meta"):
                src = element.get("content")
            else:
                src = element.get("src")

            if not src:
                continue

            src = urljoin(base_url, src)
            if src not in images:
                images.append(src)

        if images:
            break

    return images


def _build_seo_fields(title: str, price_nis: float | None) -> dict[str, str]:
    seo_title = f"Achetez {title} en ligne | Produit importé"
    price_part = f" au prix de {price_nis:.2f} ₪" if price_nis is not None else ""
    seo_description = (
        f"Découvrez {title}{price_part} sur Tavliney. Importez facilement ce produit dans votre boutique Shopify avec images, prix et SEO optimisé."
    )
    return {
        "seo_title": _clean_text(seo_title),
        "seo_description": _clean_text(seo_description),
    }


def _extract_product_details(url: str, headers: dict[str, str]) -> dict:
    response = requests.get(url, headers=headers, timeout=15)
    response.raise_for_status()
    response.encoding = response.apparent_encoding
    soup = BeautifulSoup(response.text, "lxml")

    title = _clean_text(
        (soup.find("h1") or soup.find("h2") or soup.find("title")).get_text(strip=True)
        if soup.find("h1") or soup.find("h2") or soup.find("title")
        else ""
    )

    description_tag = (
        soup.find("meta", attrs={"name": "description"}) or
        soup.find("meta", attrs={"property": "og:description"})
    )
    description = _clean_text(description_tag.get("content", "")) if description_tag else ""
    if not description:
        desc_section = (
            soup.select_one('.product-description') or
            soup.select_one('.description') or
            soup.select_one('.short-description') or
            soup.select_one('.product-info') or
            soup.select_one('#Description')
        )
        if desc_section:
            description = _clean_text(desc_section.get_text(separator=' ', strip=True))
    if not description:
        first_paragraph = soup.find('p')
        if first_paragraph:
            description = _clean_text(first_paragraph.get_text(separator=' ', strip=True))
    if not description:
        description = f"Produit importé de Tavliney pour IsraelMarket.shop. Découvrez ce produit en ligne avec livraison rapide."

    price_nis = _extract_price_from_soup(soup)
    price_eur = _price_eur_from_nis(price_nis)

    images = _extract_images(soup, url)
    if not images:
        images = [urljoin(BASE_URL, img.get("src")) for img in soup.find_all("img") if img.get("src")]

    seo = _build_seo_fields(title or url, price_nis)
    if not description:
        seo_description = seo["seo_description"]
    else:
        seo_description = description

    return {
        "nom": title or url,
        "url": url,
        "description": description,
        "price_nis": price_nis,
        "price_eur": price_eur,
        "currency_nis": "ILS",
        "currency_eur": "EUR",
        "images": images,
        "seo_title": seo["seo_title"],
        "seo_description": seo_description,
        "provider": "tavliney"
    }


def scraper(url: str) -> list[dict]:
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    response = requests.get(url, headers=headers, timeout=15)
    response.raise_for_status()
    response.encoding = response.apparent_encoding
    soup = BeautifulSoup(response.text, "lxml")

    produits = []
    seen_urls = set()

    for lien in soup.find_all("a", href=True):
        href = lien.get("href")
        if not href or "ProductInfo.asp" not in href:
            continue

        product_url = urljoin(BASE_URL, href)
        if product_url in seen_urls:
            continue

        nom = _clean_text(lien.get_text(strip=True))
        if not nom:
            nom = None

        try:
            details = _extract_product_details(product_url, headers)
            if nom:
                details["nom"] = nom
            produits.append(details)
            seen_urls.add(product_url)
        except Exception:
            if nom:
                produits.append({
                    "nom": nom,
                    "url": product_url,
                    "price_nis": None,
                    "price_eur": None,
                    "images": [],
                    "description": "",
                    "seo_title": _build_seo_fields(nom, None)["seo_title"],
                    "seo_description": _build_seo_fields(nom, None)["seo_description"],
                    "provider": "tavliney"
                })
                seen_urls.add(product_url)

    return produits
