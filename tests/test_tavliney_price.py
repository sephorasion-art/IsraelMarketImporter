from bs4 import BeautifulSoup

from scrapers.tavliney import _extract_price_from_soup, _parse_price, _price_eur_from_nis


def test_parse_price_common_formats():
    assert _parse_price("₪ 12.90") == 12.9
    assert _parse_price("12,90 ₪") == 12.9
    assert _parse_price("1,234.50") == 1234.5
    assert _parse_price("1.234,50") == 1234.5


def test_extract_price_from_meta_tag():
    html = '<html><head><meta property="product:price:amount" content="59.90"></head></html>'
    soup = BeautifulSoup(html, "lxml")
    assert _extract_price_from_soup(soup) == 59.9


def test_extract_price_from_jsonld_offer():
    html = '''
    <html><head>
      <script type="application/ld+json">
        {"@context":"https://schema.org","@type":"Product","offers":{"@type":"Offer","price":"88.40","priceCurrency":"ILS"}}
      </script>
    </head><body></body></html>
    '''
    soup = BeautifulSoup(html, "lxml")
    assert _extract_price_from_soup(soup) == 88.4


def test_price_eur_from_nis_conversion():
    assert _price_eur_from_nis(None) is None
    assert _price_eur_from_nis(40.0) == 10.0
    assert _price_eur_from_nis(18.9) == 4.72
