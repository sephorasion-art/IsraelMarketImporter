import re
from scrapers import tavliney


def _normalize_url(url: str) -> str:
    if not url:
        return url
    url = url.strip()
    # remove surrounding punctuation like (), [], <>, quotes
    url = re.sub(r'^[\(\[\<"\']+', '', url)
    url = re.sub(r'[\)\]\>\,"\']+$', '', url)
    # add scheme if missing
    if not re.match(r'^[a-zA-Z]+://', url):
        url = 'https://' + url
    return url


def importer(url):
    url = _normalize_url(url)

    if "tavlineypereg.co.il" in url:
        return tavliney.scraper(url)

    raise Exception("Fournisseur non supporté")