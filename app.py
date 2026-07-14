from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

import io, csv, json, re

from deep_translator import GoogleTranslator
from engine.parser import ImportPipeline
from engine.models import RuntimeOptions
from exporters.shopify_csv import SHOPIFY_HEADERS
import zipfile, os, requests
from urllib.parse import urlparse

app = FastAPI(title="Israel Market Importer")

templates = Jinja2Templates(directory="templates")

translator = GoogleTranslator(source='auto', target='fr')
_translation_cache = {}
pipeline = ImportPipeline()


def _extract_debug_metric(logs: list[str], prefix: str, default: int = 0) -> int:
    for line in logs:
        if line.startswith(prefix):
            match = re.search(r"(\d+)", line)
            if match:
                try:
                    return int(match.group(1))
                except ValueError:
                    return default
    return default


def _site_label_from_url(url: str) -> str:
    host = (urlparse(url).netloc or "").lower().replace("www.", "")
    if not host:
        return "Inconnu"
    return host.split(".")[0].capitalize()


def _build_analysis_context(url: str, result, produits: list[dict]) -> dict:
    execution_logs = [f"[{entry.level}] {entry.message}" for entry in result.logs]

    js_enabled = bool(
        result.detection.is_react
        or result.detection.is_nextjs
        or any(
            tech.lower() in {"react", "nextjs", "vue", "angular", "nuxt", "astro", "alpine"}
            for tech in result.detection.technologies
        )
    )
    api_count = _extract_debug_metric(execution_logs, "[info] Debug API détectées:")
    json_count = _extract_debug_metric(execution_logs, "[info] Debug réponses JSON:")

    has_images = any(bool((p.get("image") or "").strip() or p.get("gallery") or p.get("images")) for p in produits)
    has_prices = any(p.get("price") is not None for p in produits)

    return {
        "analysis_ready": True,
        "detected_site": _site_label_from_url(url),
        "detected_domain": result.detection.domain,
        "detected_tech": ", ".join(result.detection.technologies),
        "detected_cms": result.detection.cms,
        "javascript_enabled": "Oui" if js_enabled else "Non",
        "detected_api_count": api_count,
        "detected_json_count": json_count,
        "products_found": len(produits),
        "has_images": "Oui" if has_images else "Non",
        "has_prices": "Oui" if has_prices else "Non",
        "engine_used": result.engine_used,
        "analysis_time": result.elapsed_ms,
        "execution_logs": execution_logs,
    }


def _clean_text(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text.strip())


def _translate_to_french(text: str) -> str:
    """Translate text to French using deep-translator with a small cache."""
    if not text:
        return ""
    text = _clean_text(text)
    if not text:
        return ""
    if text in _translation_cache:
        return _translation_cache[text]
    try:
        translated = translator.translate(text)
        if translated:
            _translation_cache[text] = translated
            return translated
    except Exception:
        pass
    return text


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


def _first_remote_image(images):
    def _is_tracking_url(url: str) -> bool:
        if not url:
            return False
        u = url.lower()
        return any(x in u for x in ("facebook.com/tr", "facebook.com/tr?", "google-analytics", "doubleclick", "pixel", "analytics"))

    def _is_product_image(url: str) -> bool:
        if not url or not isinstance(url, str):
            return False
        u = url.split('?')[0].lower()
        if '/productsimages/' in u or '/productsimages' in u:
            return True
        return u.endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp'))

    imgs = [img for img in (images or []) if isinstance(img, str) and img.startswith(('http://', 'https://')) and not _is_tracking_url(img)]
    for img in imgs:
        if _is_product_image(img):
            return img
    return imgs[0] if imgs else ''


def _price_eur(product):
    if product.get('price_eur') is not None:
        price = _parse_price(product.get('price_eur'))
        if price is not None:
            return price
    for key in ['price_nis', 'price_ils', 'price', 'prix']:
        raw = product.get(key)
        if raw is None:
            continue
        price = _parse_price(raw)
        if price is not None:
            return round(price * 0.25, 2)
    return None


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={}
    )


@app.post("/analyser", response_class=HTMLResponse)
async def analyser_page(
    request: Request,
    url: str = Form(...),
    proxy_url: str = Form(""),
    cookie_header: str = Form(""),
    user_agent: str = Form(""),
):

    try:
        options = RuntimeOptions(
            proxy_url=proxy_url.strip() or None,
            cookie_header=cookie_header.strip() or None,
            user_agent=user_agent.strip() or None,
            debug=True,
        )
        result = pipeline.run(url, options=options)
        produits = [p.model_dump() for p in result.products]
        context = _build_analysis_context(url, result, produits)

        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={
                "url": url,
                "message": "Analyse terminée",
                "proxy_url": proxy_url,
                "cookie_header": cookie_header,
                "user_agent": user_agent,
                **context,
            },
        )
    except Exception as e:
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={
                "url": url,
                "message": f"❌ Erreur : {str(e)}",
                "proxy_url": proxy_url,
                "cookie_header": cookie_header,
                "user_agent": user_agent,
            },
        )


@app.post("/importer", response_class=HTMLResponse)
async def importer_page(
    request: Request,
    url: str = Form(...),
    proxy_url: str = Form(""),
    cookie_header: str = Form(""),
    user_agent: str = Form(""),
):

    try:
        options = RuntimeOptions(
            proxy_url=proxy_url.strip() or None,
            cookie_header=cookie_header.strip() or None,
            user_agent=user_agent.strip() or None,
            debug=True,
        )
        result = pipeline.run(url, options=options)
        produits = [p.model_dump() for p in result.products]

        # Apply live French translation to product fields
        try:
            for p in produits:
                title = p.get('title') or p.get('nom') or ''
                desc = p.get('description') or ''
                p['nom'] = _translate_to_french(title)
                p['description'] = _translate_to_french(desc)
                if p.get('price') is None and p.get('prix') is not None:
                    p['price'] = p['prix']
                if p.get('images') is None:
                    # keep compatibility with existing UI select list
                    gallery = p.get('gallery') if isinstance(p.get('gallery'), list) else []
                    p['images'] = gallery
        except Exception:
            pass

        analysis_context = _build_analysis_context(url, result, produits)

        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={
                "url": url,
                "produits": produits,
                "message": f"✅ {len(produits)} produits trouvés",
                "proxy_url": proxy_url,
                "cookie_header": cookie_header,
                "user_agent": user_agent,
                **analysis_context,
            }
        )

    except Exception as e:

        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={
                "url": url,
                "message": f"❌ Erreur : {str(e)}",
                "proxy_url": proxy_url,
                "cookie_header": cookie_header,
                "user_agent": user_agent,
            }
        )


@app.post('/export')
async def export_csv(request: Request):
    """Generate a Shopify-compatible CSV from selected products (form fields: products_json, selected)
    Returns attachment CSV.
    """
    form = await request.form()
    products_json = form.get('products_json')
    if not products_json:
        return HTMLResponse('Missing products data', status_code=400)

    try:
        products = json.loads(products_json)
    except Exception:
        return HTMLResponse('Invalid products data', status_code=400)

    selected = form.getlist('selected')
    if not selected:
        # if none selected, default to all
        selected_idx = range(len(products))
    else:
        try:
            selected_idx = [int(i) for i in selected]
        except Exception:
            return HTMLResponse('Invalid selection', status_code=400)

    # Build CSV in memory
    sio = io.StringIO()
    writer = csv.DictWriter(sio, fieldnames=SHOPIFY_HEADERS)
    writer.writeheader()

    for i in selected_idx:
        if i < 0 or i >= len(products):
            continue
        p = products[i]
        title = p.get('nom') or p.get('title') or ''
        title = _translate_to_french(title)
        description = p.get('description') or p.get('seo_description') or ''
        description = _translate_to_french(description) if description else ''
        if not description:
            description = f"Découvrez {title} sur IsraelMarket.shop avec livraison rapide, service client expert et qualité israélienne."
        seo_title = p.get('seo_title') or f"Achetez {title} en ligne | IsraelMarket.shop"
        seo_description = p.get('seo_description') or description
        handle = (title or p.get('url','')).lower()
        handle = ''.join(c if c.isalnum() else '-' for c in handle)[:200]
        price = ''
        eur_price = _price_eur(p)
        if eur_price is not None:
            price = f"{eur_price:.2f}"
        # allow user override from per-product select (form fields named image_{index})
        override = form.get(f'image_{i}')
        image_src = ''
        if override:
            try:
                if isinstance(override, str) and override.startswith(('http://', 'https://')):
                    # avoid tracking pixels
                    if not any(x in override.lower() for x in ("facebook.com/tr", "google-analytics", "doubleclick", "pixel", "analytics")):
                        image_src = override
            except Exception:
                image_src = ''
        if not image_src:
            image_src = _first_remote_image(p.get('images') or [])
            if image_src and not image_src.startswith(('http://', 'https://')):
                image_src = ''

        row = {
            'Handle': handle,
            'Title': title,
            'Body (HTML)': description,
            'Vendor': 'IsraelMarket.shop',
            'Type': p.get('type', ''),
            'Tags': ', '.join(p.get('tags', [])) if isinstance(p.get('tags'), list) else p.get('tags', ''),
            'Published': 'TRUE',
            'Option1 Name': 'Title',
            'Option1 Value': 'Default Title',
            'Option2 Name': '',
            'Option2 Value': '',
            'Option3 Name': '',
            'Option3 Value': '',
            'Variant SKU': p.get('sku', ''),
            'Variant Grams': '',
            'Variant Inventory Tracker': '',
            'Variant Inventory Qty': p.get('inventory_qty', ''),
            'Variant Inventory Policy': 'deny',
            'Variant Fulfillment Service': 'manual',
            'Variant Price': price,
            'Variant Compare At Price': '',
            'Variant Requires Shipping': 'TRUE',
            'Variant Taxable': 'TRUE',
            'Variant Barcode': '',
            'Image Src': image_src,
            'Image Position': 1 if image_src else '',
            'Image Alt Text': title,
            'Gift Card': 'FALSE',
            'SEO Title': seo_title,
            'SEO Description': seo_description,
            'Google Shopping / Google Product Category': '',
            'Google Shopping / Gender': '',
            'Google Shopping / Age Group': '',
            'Google Shopping / MPN': '',
            'Google Shopping / AdWords Grouping': '',
            'Google Shopping / AdWords Labels': '',
            'Google Shopping / Condition': 'new',
            'Google Shopping / Custom Product': '',
            'Google Shopping / Custom Label 0': '',
            'Google Shopping / Custom Label 1': '',
            'Google Shopping / Custom Label 2': '',
            'Google Shopping / Custom Label 3': '',
            'Google Shopping / Custom Label 4': '',
            'Variant Image': image_src,
            'Variant Weight Unit': 'kg',
            'Status': 'active'
        }

        writer.writerow(row)

    sio.seek(0)
    headers = {
        'Content-Disposition': 'attachment; filename="shopify_export_selected.csv"'
    }
    return StreamingResponse(iter([sio.getvalue().encode('utf-8')]), media_type='text/csv', headers=headers)


@app.post('/export_zip')
async def export_zip(request: Request):
    """Generate a ZIP containing the Shopify CSV and the selected images."""
    form = await request.form()
    products_json = form.get('products_json')
    if not products_json:
        return HTMLResponse('Missing products data', status_code=400)

    try:
        products = json.loads(products_json)
    except Exception:
        return HTMLResponse('Invalid products data', status_code=400)

    selected = form.getlist('selected')
    if not selected:
        selected_idx = range(len(products))
    else:
        try:
            selected_idx = [int(i) for i in selected]
        except Exception:
            return HTMLResponse('Invalid selection', status_code=400)

    # Prepare CSV in memory and collect images into a zip
    sio = io.StringIO()
    writer = csv.DictWriter(sio, fieldnames=SHOPIFY_HEADERS)
    writer.writeheader()

    files_to_add = []  # tuples (arcname, bytes)

    for i in selected_idx:
        if i < 0 or i >= len(products):
            continue
        p = products[i]
        title = p.get('nom') or p.get('title') or ''
        title = _translate_to_french(title)
        description = p.get('description') or p.get('seo_description') or ''
        description = _translate_to_french(description) if description else ''
        if not description:
            description = f"Découvrez {title} sur IsraelMarket.shop avec livraison rapide, service client expert et qualité israélienne."
        seo_title = p.get('seo_title') or f"Achetez {title} en ligne | IsraelMarket.shop"
        seo_description = p.get('seo_description') or description
        handle = (title or p.get('url','')).lower()
        handle = ''.join(c if c.isalnum() else '-' for c in handle)[:200]
        price = ''
        eur_price = _price_eur(p)
        if eur_price is not None:
            price = f"{eur_price:.2f}"

        # image override or pick first
        override = form.get(f'image_{i}')
        chosen = None
        if override:
            chosen = override
        if not chosen:
            chosen = _first_remote_image(p.get('images') or [])

        image_filename = ''
        if chosen:
            # if it's a local downloaded path, include that file
            if chosen.startswith('downloads/') or chosen.startswith('./downloads/'):
                local_path = os.path.join(os.getcwd(), chosen)
                if os.path.exists(local_path):
                    image_filename = os.path.basename(local_path)
                    with open(local_path, 'rb') as fh:
                        files_to_add.append((image_filename, fh.read()))
            elif chosen.startswith('http://') or chosen.startswith('https://'):
                # download remote image into zip
                try:
                    r = requests.get(chosen, timeout=20)
                    if r.status_code == 200 and r.content:
                        path = urlparse(chosen).path
                        ext = os.path.splitext(path)[1] or '.jpg'
                        image_filename = f"{handle}{ext}"
                        files_to_add.append((image_filename, r.content))
                except Exception:
                    image_filename = ''

        row = {
            'Handle': handle,
            'Title': title,
            'Body (HTML)': description,
            'Vendor': 'IsraelMarket.shop',
            'Type': p.get('type', ''),
            'Tags': ', '.join(p.get('tags', [])) if isinstance(p.get('tags'), list) else p.get('tags', ''),
            'Published': 'TRUE',
            'Option1 Name': 'Title',
            'Option1 Value': 'Default Title',
            'Option2 Name': '',
            'Option2 Value': '',
            'Option3 Name': '',
            'Option3 Value': '',
            'Variant SKU': p.get('sku', ''),
            'Variant Grams': '',
            'Variant Inventory Tracker': '',
            'Variant Inventory Qty': p.get('inventory_qty', ''),
            'Variant Inventory Policy': 'deny',
            'Variant Fulfillment Service': 'manual',
            'Variant Price': price,
            'Variant Compare At Price': '',
            'Variant Requires Shipping': 'TRUE',
            'Variant Taxable': 'TRUE',
            'Variant Barcode': '',
            'Image Src': image_filename,
            'Image Position': 1 if image_filename else '',
            'Image Alt Text': title,
            'Gift Card': 'FALSE',
            'SEO Title': seo_title,
            'SEO Description': seo_description,
            'Google Shopping / Google Product Category': '',
            'Google Shopping / Gender': '',
            'Google Shopping / Age Group': '',
            'Google Shopping / MPN': '',
            'Google Shopping / AdWords Grouping': '',
            'Google Shopping / AdWords Labels': '',
            'Google Shopping / Condition': 'new',
            'Google Shopping / Custom Product': '',
            'Google Shopping / Custom Label 0': '',
            'Google Shopping / Custom Label 1': '',
            'Google Shopping / Custom Label 2': '',
            'Google Shopping / Custom Label 3': '',
            'Google Shopping / Custom Label 4': '',
            'Variant Image': image_filename,
            'Variant Weight Unit': 'kg',
            'Status': 'active'
        }

        writer.writerow(row)

    # build zip in memory
    mem = io.BytesIO()
    with zipfile.ZipFile(mem, mode='w', compression=zipfile.ZIP_DEFLATED) as zf:
        # add CSV
        sio.seek(0)
        zf.writestr('shopify_export_selected.csv', sio.getvalue())
        # add images
        for arcname, data in files_to_add:
            zf.writestr(arcname, data)

    mem.seek(0)
    headers = {'Content-Disposition': 'attachment; filename="shopify_export_with_images.zip"'}
    return StreamingResponse(mem, media_type='application/zip', headers=headers)