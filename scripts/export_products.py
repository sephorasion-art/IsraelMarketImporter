#!/usr/bin/env python3
# Fetch products via importer, save JSON, create HTML list, download images, generate Shopify CSV
import os, json, csv, re, requests
from urllib.parse import urlparse

from deep_translator import GoogleTranslator

from exporters.shopify_csv import export_products as export_shopify_csv
from scrapers.router import importer

translator = GoogleTranslator(source='auto', target='fr')
translation_cache = {}

OUT_DIR = "downloads"
IMAGES_DIR = os.path.join(OUT_DIR, "images")
os.makedirs(IMAGES_DIR, exist_ok=True)

URL = "https://www.tavlineypereg.co.il"

print('Fetching products from', URL)
products = importer(URL)
print('Found', len(products), 'products')

# Save raw JSON
with open(os.path.join(OUT_DIR, 'products.json'), 'w', encoding='utf-8') as f:
    json.dump(products, f, ensure_ascii=False, indent=2)

# Helper slug
def slug(text: str) -> str:
    if not text:
        return 'product'
    s = text.lower()
    s = re.sub(r"[^a-z0-9]+", '-', s)
    s = re.sub(r"-+", '-', s).strip('-')
    return s or 'product'


def _clean_text(text: str) -> str:
    if not text:
        return ''
    return re.sub(r"\s+", ' ', text.strip())


def _parse_price(value):
    if value is None:
        return None
    s = str(value).strip()
    s = re.sub(r"[^0-9,\.]+", "", s)
    s = s.replace(',', '.')
    try:
        return float(s)
    except Exception:
        return None


def _price_eur(product):
    if product.get('price_eur') is not None:
        parsed = _parse_price(product.get('price_eur'))
        if parsed is not None:
            return parsed
    for key in ['price_nis', 'price_ils', 'price', 'prix']:
        raw = product.get(key)
        if raw is None:
            continue
        parsed = _parse_price(raw)
        if parsed is not None:
            return round(parsed * ILS_TO_EUR, 2)
    return None


def _translate(text: str) -> str:
    if not text:
        return ''
    text = _clean_text(text)
    if not text:
        return ''
    if text in translation_cache:
        return translation_cache[text]
    try:
        translated = translator.translate(text)
        translation_cache[text] = translated
        return translated
    except Exception:
        return text


def _first_remote_image(images):
    imgs = _filter_and_prioritize_images(images)
    return imgs[0] if imgs else ''


def _is_tracking_url(url: str) -> bool:
    if not url:
        return False
    u = url.lower()
    return any(x in u for x in ("facebook.com/tr", "facebook.com/tr?", "google-analytics", "doubleclick", "pixel", "analytics"))


def _is_product_image(url: str) -> bool:
    if not url or not isinstance(url, str):
        return False
    u = url.split('?')[0].lower()
    return '/productsimages/' in u or '/productsimages' in u


def _filter_and_prioritize_images(images):
    imgs = [img for img in (images or []) if isinstance(img, str) and img.startswith(('http://', 'https://'))]
    imgs = [i for i in imgs if not _is_tracking_url(i)]
    product_specific = [i for i in imgs if '/productsimages/' in i.lower() or '/productsimages' in i.lower()]
    others = [i for i in imgs if i not in product_specific]
    return product_specific + others


def make_seo_description(title: str, description: str) -> str:
    seo = []
    if title:
        seo.append(f"<h1>{title}</h1>")
    if description:
        seo.append(f"<p>{description}</p>")
    seo.append('<p><strong>IsraelMarket.shop</strong> — produits importés d’Israël, qualité premium, livraison rapide.</p>')
    seo.append('<p>Idéal pour cadeaux, cuisine israélienne, épicerie fine, gastronomie locale.</p>')
    return '\n'.join(seo)


# Download images
for p in products:
    imgs = p.get('images') or []
    saved = []
    for i, src in enumerate(imgs):
        try:
            if not src:
                continue
            r = requests.get(src, timeout=20)
            if r.status_code != 200:
                continue
            path = urlparse(src).path
            ext = os.path.splitext(path)[1] or '.jpg'
            name = slug(p.get('nom') or p.get('title') or p.get('url'))
            fname = f"{name}_{i}{ext}"
            fname = re.sub(r'[^A-Za-z0-9._-]', '_', fname)
            dest = os.path.join(IMAGES_DIR, fname)
            with open(dest, 'wb') as out:
                out.write(r.content)
            saved.append(dest)
        except Exception:
            continue
    p['_downloaded_images'] = saved

# Create simple HTML listing
html_path = os.path.join(OUT_DIR, 'products.html')
with open(html_path, 'w', encoding='utf-8') as f:
    f.write('<!doctype html><html><head><meta charset="utf-8"><title>Products</title></head><body>')
    f.write(f'<h1>{len(products)} products</h1>')
    for p in products:
        title = p.get('nom') or p.get('title') or ''
        url = p.get('url') or ''
        f.write('<div style="margin-bottom:24px;">')
        f.write(f'<h2>{title}</h2>')
        f.write(f'<div><a href="{url}" target="_blank">{url}</a></div>')
        imgs = p.get('_downloaded_images', [])
        if imgs:
            for img in imgs:
                rel = os.path.relpath(img, OUT_DIR)
                f.write(f'<div><img src="{rel}" style="max-width:220px;"/></div>')
        f.write('</div><hr/>')
    f.write('</body></html>')

csv_path = os.path.join(OUT_DIR, 'shopify_export.csv')
full_csv_path = os.path.join(OUT_DIR, 'shopify_export_full.csv')
fields = ['Handle','Title','Body (HTML)','Vendor','Type','Tags','Published','Variant Price','Image Src']
# Conversion rate ILS -> EUR (approx). Adjust if needed.
ILS_TO_EUR = 0.25

for p in products:
    title = p.get('nom') or p.get('title') or ''
    if title:
        p['nom'] = _translate(title)
    desc = p.get('description') or ''
    if desc:
        p['description'] = _translate(desc)
    p['seo_description'] = make_seo_description(p['nom'], p['description'])
    p['seo_title'] = f"Achetez {p['nom']} en ligne | IsraelMarket.shop"

    p_eur = _price_eur(p)
    p['price_eur'] = p_eur

    # Ensure CSV export uses only remote image URLs for Shopify compatibility
    if p.get('images'):
        p['images'] = _filter_and_prioritize_images(p['images'])

with open(csv_path, 'w', encoding='utf-8', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    for p in products:
        title = p.get('nom') or p.get('title') or ''
        handle = slug(title) or slug(p.get('url', 'product'))
        desc = p.get('description') or ''
        price_val = ''
        eur_price = p.get('price_eur')
        if eur_price is not None:
            try:
                price_val = float(str(eur_price).replace(',', '.'))
            except Exception:
                price_val = ''
        img = _first_remote_image(p.get('images') or [])
        writer.writerow({'Handle': handle, 'Title': title, 'Body (HTML)': desc, 'Vendor': '', 'Type': '', 'Tags': '', 'Published': 'TRUE', 'Variant Price': price_val, 'Image Src': img})

# Export a complete Shopify CSV using the standardized exporter
export_shopify_csv(products, full_csv_path)

print('Saved:', json.dumps({
    'json': os.path.join(OUT_DIR, 'products.json'),
    'html': html_path,
    'csv': csv_path,
    'full_csv': full_csv_path,
    'images_dir': IMAGES_DIR
}, ensure_ascii=False))
