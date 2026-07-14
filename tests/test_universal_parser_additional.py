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


def test_universal_parser_extracts_opengraph_and_meta_fields():
    html = '''
    <html><head>
      <meta property="og:title" content="OG Product" />
      <meta property="og:description" content="OG Description" />
      <meta property="og:image" content="https://example.com/og.jpg" />
      <meta property="product:price:amount" content="88.40" />
      <meta property="product:original_price:amount" content="99.90" />
      <meta property="product:sku" content="OG-SKU-1" />
      <meta property="product:ean" content="1234567890123" />
      <meta property="product:brand" content="OG Brand" />
      <meta property="product:category" content="Snacks" />
      <meta name="keywords" content="chips,salty,party" />
      <meta property="product:availability" content="in stock" />
    </head><body></body></html>
    '''
    parser = UniversalParser()
    products = parser.parse(html)

    assert len(products) == 1
    p = products[0]
    assert p["title"] == "OG Product"
    assert p["price"] == 88.4
    assert p["compare_at_price"] == 99.9
    assert p["sku"] == "OG-SKU-1"
    assert p["ean"] == "1234567890123"
    assert p["brand"] == "OG Brand"
    assert p["category"] == "Snacks"
    assert p["stock"] == 1
    assert p["image"] == "https://example.com/og.jpg"
    assert p["confidence"] > 0


def test_universal_parser_fallback_merges_strategies_with_confidence():
    html = '''
    <html><head>
      <script type="application/ld+json">
      {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": "Merged Product",
        "sku": "MERGE-1",
        "offers": {"@type": "Offer", "price": "45.50"}
      }
      </script>
    </head>
    <body>
      <div class="product-card">
        <h2 class="product-title">Merged Product</h2>
        <p class="description">Great product for testing</p>
        <img src="/img/merged.jpg" />
        <a href="/p/merge-1">Voir</a>
      </div>
    </body></html>
    '''

    parser = UniversalParser()
    products = parser.parse(html, base_url="https://example.com")

    assert len(products) == 1
    p = products[0]
    assert p["title"] == "Merged Product"
    assert p["price"] == 45.5
    assert p["image"] == "https://example.com/img/merged.jpg"
    assert p["url"] == "https://example.com/p/merge-1"
    assert p["confidence"] > 0
    assert isinstance(p["confidence_by_field"], dict)
    assert "price" in p["confidence_by_field"]
