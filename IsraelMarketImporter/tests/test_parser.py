from engine.playwright_engine import PlaywrightEngine
from engine.parser import UniversalParser

url = "https://deli.yango.com/en-il/catalog/grocery/category/snacks"

engine = PlaywrightEngine()

html = engine.get_html(url)

parser = UniversalParser()

products = parser.parse(html)

print(f"Produits trouvés : {len(products)}")

for p in products[:10]:
    print("--------------------------------")
    print(p.title)
    print(p.price)
    print(p.image)
    print(p.url)