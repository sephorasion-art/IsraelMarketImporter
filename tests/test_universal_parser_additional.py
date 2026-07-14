from engine.universal_parser import UniversalParser


def test_universal_parser_application_json_product():
    html = '''
    <html><head>
      <script type="application/json">
      {"name":"API Product","description":"From API","sku":"API123","offers":{"price":"12.34","priceCurrency":"EUR"},"image":"https://example.com/api-image.jpg"}
      </script>
    </head><body></body></html>
    '''
    parser = UniversalParser()
    products = parser.parse(html)

    assert len(products) == 1
    p = products[0]
    assert p["title"] == "API Product"
    assert p["price"] == 12.34
    assert p["currency"] == "EUR"
    assert p["images"] == ["https://example.com/api-image.jpg"]


def test_universal_parser_jsonld_graph():
    html = '''
    <html><head>
      <script type="application/ld+json">
      {"@context":"http://schema.org/","@graph":[{"@type":"Product","name":"Graph Product","offers":{"@type":"Offer","price":"9.99","priceCurrency":"EUR"}}]}
      </script>
    </head><body></body></html>
    '''
    parser = UniversalParser()
    products = parser.parse(html)

    assert len(products) == 1
    p = products[0]
    assert p["title"] == "Graph Product"
    assert p["price"] == 9.99
    assert p["currency"] == "EUR"


def test_universal_parser_parse_api_payloads_nested_products():
    parser = UniversalParser()
    payloads = [
      {
        "data": {
          "catalog": {
            "items": [
              {
                "id": "p1",
                "name": "Chips Paprika",
                "pricing": {"amount": "12.50"},
                "images": [{"url": "https://example.com/chips.jpg"}],
                "url": "https://example.com/p/chips",
              },
              {
                "id": "p2",
                "displayName": "Cola Zero",
                "priceInfo": {"value": "7,90"},
                "image": "https://example.com/cola.jpg",
              },
            ]
          }
        }
      }
    ]

    products = parser.parse_api_payloads(payloads)
    titles = {p.title for p in products}
    assert "Chips Paprika" in titles
    assert "Cola Zero" in titles
    assert len(products) >= 2
