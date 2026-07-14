#!/usr/bin/env python3
import os, json, csv, re
from urllib.parse import urlparse

OUT_DIR = "downloads"
IMAGES_DIR = os.path.join(OUT_DIR, "images")
JSON_IN = os.path.join(OUT_DIR, 'products.json')
HTML_OUT = os.path.join(OUT_DIR, 'products_seo.html')
CSV_OUT = os.path.join(OUT_DIR, 'shopify_export_seo.csv')

if not os.path.exists(JSON_IN):
    raise SystemExit(f"Missing {JSON_IN} — run the exporter first")

with open(JSON_IN, 'r', encoding='utf-8') as f:
    products = json.load(f)

# slug helper
def slug(text: str) -> str:
    if not text:
        return 'product'
    s = text.lower()
    s = re.sub(r"[^a-z0-9]+", '-', s)
    s = re.sub(r"-+", '-', s).strip('-')
    return s or 'product'

# SEO description builder
def make_seo_html(p: dict) -> str:
    title = p.get('nom') or p.get('title') or ''
    orig = p.get('description') or p.get('desc') or ''
    # Preserve Hebrew and original text; add SEO phrases and brand mention
    seo = []
    seo.append(f"<h1>{title}</h1>")
    if orig:
        seo.append(f"<p>{orig}</p>")
    seo.append('<p><strong>IsraelMarket.shop</strong> — livraison rapide en Israël, qualité garantie. Acheter en ligne aujourd\'hui.</p>')
    # Add small keyword sentence (French + Hebrew)
    seo.append('<p>Épices, épicerie fine, produits locaux — קניות אונליין, משלוח מהיר.</p>')
    return '\n'.join(seo)

# Parse numeric price from product (if possible)
def parse_price(p: dict):
    cand = p.get('price') or p.get('prix') or p.get('price_ils') or p.get('price_text') or p.get('prix_text')
    if not cand:
        return None
    s = str(cand).strip()
    # remove non numeric except comma/dot
    s = re.sub(r"[^0-9,\.]+", '', s)
    s = s.replace(',', '.')
    try:
        return float(s)
    except Exception:
        return None

# Regenerate HTML
with open(HTML_OUT, 'w', encoding='utf-8') as f:
    f.write('<!doctype html><html><head><meta charset="utf-8"><title>Products - IsraelMarket.shop</title></head><body>')
    f.write(f'<h1>{len(products)} produits - IsraelMarket.shop</h1>')
    for p in products:
        title = p.get('nom') or p.get('title') or ''
        url = p.get('url') or ''
        price = parse_price(p)
        price_display = ''
        if price is not None:
            # ILS == EUR numeric value per request
            price_display = f"{price:.2f} €"
        f.write('<div style="margin-bottom:28px;">')
        f.write(f'<h2>{title}</h2>')
        if price_display:
            f.write(f'<div><strong>Prix: {price_display}</strong></div>')
        f.write(f'<div><a href="{url}" target="_blank">Voir le produit</a></div>')
        # description (seo)
        seo_html = make_seo_html(p)
        f.write(f'<div>{seo_html}</div>')
        imgs = p.get('_downloaded_images') or p.get('images') or []
        if imgs:
            for img in imgs:
                rel = os.path.relpath(img, OUT_DIR)
                f.write(f'<div><img src="{rel}" style="max-width:220px;"/></div>')
        f.write('</div><hr/>')
    f.write('</body></html>')

# Regenerate Shopify CSV
fields = ['Handle','Title','Body (HTML)','Vendor','Type','Tags','Published','Variant Price','Image Src']
with open(CSV_OUT, 'w', encoding='utf-8', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    for p in products:
        title = p.get('nom') or p.get('title') or ''
        handle = slug(title) or slug(p.get('url','product'))
        seo_html = make_seo_html(p)
        price = parse_price(p)
        price_val = ''
        if price is not None:
            # Use same numeric value as ILS but mark as EUR per user's rule
            price_val = f"{price:.2f}"
        img = ''
        imgs = p.get('_downloaded_images') or p.get('images') or []
        if imgs:
            img0 = imgs[0]
            if img0.startswith(IMAGES_DIR):
                img = os.path.relpath(img0, OUT_DIR)
            else:
                img = img0
        writer.writerow({'Handle': handle, 'Title': title, 'Body (HTML)': seo_html, 'Vendor': 'IsraelMarket.shop', 'Type': '', 'Tags': '', 'Published': 'TRUE', 'Variant Price': price_val, 'Image Src': img})

print('Regenerated:', HTML_OUT, CSV_OUT)
