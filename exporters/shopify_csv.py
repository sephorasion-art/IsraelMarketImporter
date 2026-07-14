import csv
from pathlib import Path
from typing import Iterable


SHOPIFY_HEADERS = [
    "Handle",
    "Title",
    "Body (HTML)",
    "Vendor",
    "Type",
    "Tags",
    "Published",
    "Option1 Name",
    "Option1 Value",
    "Option2 Name",
    "Option2 Value",
    "Option3 Name",
    "Option3 Value",
    "Variant SKU",
    "Variant Grams",
    "Variant Inventory Tracker",
    "Variant Inventory Qty",
    "Variant Inventory Policy",
    "Variant Fulfillment Service",
    "Variant Price",
    "Variant Compare At Price",
    "Variant Requires Shipping",
    "Variant Taxable",
    "Variant Barcode",
    "Image Src",
    "Image Position",
    "Image Alt Text",
    "Gift Card",
    "SEO Title",
    "SEO Description",
    "Google Shopping / Google Product Category",
    "Google Shopping / Gender",
    "Google Shopping / Age Group",
    "Google Shopping / MPN",
    "Google Shopping / AdWords Grouping",
    "Google Shopping / AdWords Labels",
    "Google Shopping / Condition",
    "Google Shopping / Custom Product",
    "Google Shopping / Custom Label 0",
    "Google Shopping / Custom Label 1",
    "Google Shopping / Custom Label 2",
    "Google Shopping / Custom Label 3",
    "Google Shopping / Custom Label 4",
    "Variant Image",
    "Variant Weight Unit",
    "Status"
]


def _normalize_handle(title: str) -> str:
    handle = title.lower().strip()
    handle = handle.replace(" ", "-")
    handle = handle.replace("/", "-")
    return handle


def _is_tracking_url(url: str) -> bool:
    if not url:
        return False
    u = url.lower()
    return any(x in u for x in ("facebook.com/tr", "facebook.com/tr?", "google-analytics", "doubleclick", "pixel", "analytics"))


def _is_product_image(url: str) -> bool:
    # Strict product image: specifically hosted under ProductsImages path on site
    if not url or not isinstance(url, str):
        return False
    u = url.split('?')[0].lower()
    return '/productsimages/' in u or '/productsimages' in u


def _filter_and_prioritize_images(images):
    imgs = [img for img in (images or []) if isinstance(img, str) and img.startswith(('http://', 'https://'))]
    imgs = [i for i in imgs if not _is_tracking_url(i)]
    # product-specific images (ProductsImages) first, then other valid images
    product_specific = [i for i in imgs if '/productsimages/' in i.lower() or '/productsimages' in i.lower()]
    others = [i for i in imgs if i not in product_specific]
    return product_specific + others


def export_products(products: Iterable[dict], output_path: str | Path) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=SHOPIFY_HEADERS)
        writer.writeheader()

        for product in products:
            handle = _normalize_handle(product.get("nom", product.get("title", "product")))
            images = _filter_and_prioritize_images(product.get("images", []) or [])
            seo_title = product.get("seo_title") or f"Achetez {product.get('nom', product.get('title', 'produit'))} en ligne | IsraelMarket.shop"
            seo_description = product.get("seo_description") or f"Découvrez {product.get('nom', product.get('title', 'ce produit'))} sur IsraelMarket.shop avec livraison rapide et qualité premium."
            price_eur = product.get("price_eur")
            if price_eur is not None:
                try:
                    price_eur = float(price_eur)
                except Exception:
                    price_eur = None

            row = {
                "Handle": handle,
                "Title": product.get("nom", ""),
                "Body (HTML)": product.get("description", ""),
                "Vendor": product.get("provider", "Tavliney"),
                "Type": product.get("type", "Imported"),
                "Tags": ", ".join(product.get("tags", [])),
                "Published": "TRUE",
                "Option1 Name": "Title",
                "Option1 Value": "Default Title",
                "Option2 Name": "",
                "Option2 Value": "",
                "Option3 Name": "",
                "Option3 Value": "",
                "Variant SKU": product.get("sku", ""),
                "Variant Grams": "",
                "Variant Inventory Tracker": "",
                "Variant Inventory Qty": product.get("inventory_qty", ""),
                "Variant Inventory Policy": "deny",
                "Variant Fulfillment Service": "manual",
                "Variant Price": f"{price_eur:.2f}" if price_eur is not None else "",
                "Variant Compare At Price": "",
                "Variant Requires Shipping": "TRUE",
                "Variant Taxable": "TRUE",
                "Variant Barcode": "",
                "Image Src": images[0] if images else "",
                "Image Position": 1 if images else "",
                "Image Alt Text": product.get("nom", ""),
                "Gift Card": "FALSE",
                "SEO Title": seo_title,
                "SEO Description": seo_description,
                "Google Shopping / Google Product Category": "",
                "Google Shopping / Gender": "",
                "Google Shopping / Age Group": "",
                "Google Shopping / MPN": "",
                "Google Shopping / AdWords Grouping": "",
                "Google Shopping / AdWords Labels": "",
                "Google Shopping / Condition": "new",
                "Google Shopping / Custom Product": "",
                "Google Shopping / Custom Label 0": "",
                "Google Shopping / Custom Label 1": "",
                "Google Shopping / Custom Label 2": "",
                "Google Shopping / Custom Label 3": "",
                "Google Shopping / Custom Label 4": "",
                "Variant Image": images[0] if images else "",
                "Variant Weight Unit": "kg",
                "Status": "active"
            }

            writer.writerow(row)

            for idx, image_src in enumerate(images[1:], start=2):
                image_row = {key: "" for key in SHOPIFY_HEADERS}
                image_row["Handle"] = handle
                image_row["Image Src"] = image_src
                image_row["Image Position"] = idx
                image_row["Status"] = "active"
                writer.writerow(image_row)

    return output_path
