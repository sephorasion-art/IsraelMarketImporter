from engine.api_discovery_engine import ApiDiscoveryEngine


def test_api_discovery_accepts_name_plus_price_minimum_signal():
    engine = ApiDiscoveryEngine()
    payloads = [{"items": [{"name": "Only Name Price", "price": "14.90"}]}]

    products = engine.discover_products(payloads)

    assert len(products) >= 1
    assert products[0].title == "Only Name Price"
    assert products[0].price == 14.9


def test_api_discovery_extracts_nested_pricing_dicts():
    engine = ApiDiscoveryEngine()
    payloads = [
        {
            "data": {
                "products": [
                    {
                        "name": "Nested Price Product",
                        "pricing": {"amount": "9,50"},
                        "image": "https://example.com/nested.jpg",
                    }
                ]
            }
        }
    ]

    products = engine.discover_products(payloads)

    assert len(products) == 1
    assert products[0].title == "Nested Price Product"
    assert products[0].price == 9.5
