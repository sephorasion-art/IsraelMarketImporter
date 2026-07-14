from engine.universal_parser import UniversalParser


def test_universal_parser_jsonld():
    html = '''
    <html><head>
      <script type="application/ld+json">
      {"@context":"http://schema.org/","@type":"Product","name":"Test Product","description":"Test description","sku":"SKU123","offers":{"@type":"Offer","price":"49.90","priceCurrency":"EUR"},"image":["https://example.com/image1.jpg","https://example.com/image2.jpg"]}
      </script>
    </head><body></body></html>
    '''
    parser = UniversalParser()
    products = parser.parse(html)

    assert len(products) == 1
    product = products[0]
    assert product["title"] == "Test Product"
    assert product["price"] == 49.90
    assert product["currency"] == "EUR"
    assert product["images"] == ["https://example.com/image1.jpg", "https://example.com/image2.jpg"]


def test_universal_parser_dom_fallback():
    html = '''
    <html><body>
      <div class="product-card">
        <h2 class="product-title">Fallback Product</h2>
        <span class="price">€79.50</span>
        <a href="/product/1">Voir</a>
        <img src="/images/product.jpg" />
      </div>
    </body></html>
    '''
    parser = UniversalParser()
    products = parser.parse(html, base_url="https://example.com")

    assert len(products) == 1
    product = products[0]
    assert product["title"] == "Fallback Product"
    assert product["price"] == 79.50
    assert product["url"] == "https://example.com/product/1"
    assert product["images"] == ["https://example.com/images/product.jpg"]
