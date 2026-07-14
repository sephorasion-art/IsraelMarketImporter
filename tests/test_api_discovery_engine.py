from engine.api_discovery_engine import ApiDiscoveryEngine


def test_api_discovery_classifies_modern_network_urls():
    engine = ApiDiscoveryEngine()
    labels = engine.classify_url("https://example.com/api/products?format=json", "xhr")

    assert "xhr" in labels
    assert "json" in labels
    assert "api" in labels


def test_api_discovery_extracts_products_from_json_payloads():
    engine = ApiDiscoveryEngine()
    payloads = [
        {
            "data": {
                "items": [
                    {
                        "id": "p1",
                        "name": "Product One",
                        "price": "12.50",
                        "image": "https://example.com/p1.jpg",
                        "category": "Snacks",
                    },
                    {
                        "sku": "sku-2",
                        "title": "Product Two",
                        "currentPrice": 8.9,
                        "images": ["https://example.com/p2.jpg"],
                        "categoryName": "Drinks",
                    },
                ]
            }
        }
    ]

    products = engine.discover_products(payloads)

    assert len(products) >= 2
    names = {p.title for p in products}
    assert "Product One" in names
    assert "Product Two" in names
