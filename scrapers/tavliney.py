import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

BASE_URL = "https://www.tavlineypereg.co.il"


def scraper(url):

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    r = requests.get(url, headers=headers)

    r.raise_for_status()

    # Ensure correct text encoding for Hebrew content
    r.encoding = r.apparent_encoding

    soup = BeautifulSoup(r.text, "lxml")

    produits = []
    seen_urls = set()

    for lien in soup.find_all("a", href=True):

        href = lien.get("href")

        if href and "ProductInfo.asp" in href:

            nom = lien.get_text(strip=True)
            product_url = urljoin(BASE_URL, href)

            # skip duplicates by URL
            if product_url in seen_urls:
                continue

            # If link text is empty, try to fetch product page and extract a title
            if not nom:
                try:
                    pr = requests.get(product_url, headers=headers, timeout=8)
                    pr.raise_for_status()
                    pr.encoding = pr.apparent_encoding
                    ps = BeautifulSoup(pr.text, "lxml")

                    # common title locations
                    title_tag = ps.find("h1") or ps.find("h2")
                    if title_tag and title_tag.get_text(strip=True):
                        nom = title_tag.get_text(strip=True)
                    else:
                        og_title = ps.find("meta", property="og:title")
                        if og_title and og_title.get("content"):
                            nom = og_title.get("content").strip()
                        elif ps.title and ps.title.string:
                            nom = ps.title.string.strip()
                except Exception:
                    # on failure, leave name empty
                    nom = nom

            produits.append({
                "nom": nom,
                "url": product_url
            })

            seen_urls.add(product_url)

    return produits
