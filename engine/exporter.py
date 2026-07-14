from __future__ import annotations

import csv
import io

from engine.models import Product
from exporters.shopify_csv import SHOPIFY_HEADERS


class Exporter:
	"""Shopify export service (CSV + API payload preparation)."""

	def to_shopify_csv(self, products: list[Product]) -> str:
		sio = io.StringIO()
		writer = csv.DictWriter(sio, fieldnames=SHOPIFY_HEADERS)
		writer.writeheader()

		for p in products:
			handle = "".join(c if c.isalnum() else "-" for c in (p.title or p.url).lower())[:200]
			row = {h: "" for h in SHOPIFY_HEADERS}
			row.update(
				{
					"Handle": handle,
					"Title": p.title,
					"Body (HTML)": p.description,
					"Vendor": "IsraelMarket.shop",
					"Published": "TRUE",
					"Option1 Name": "Title",
					"Option1 Value": "Default Title",
					"Variant SKU": p.sku,
					"Variant Price": f"{p.price:.2f}" if p.price is not None else "",
					"Variant Compare At Price": f"{p.compare_at_price:.2f}" if p.compare_at_price is not None else "",
					"Variant Inventory Qty": p.stock if p.stock is not None else "",
					"Image Src": p.image,
					"Image Alt Text": p.title,
					"SEO Title": p.title[:70],
					"SEO Description": p.description[:160],
					"Variant Image": p.image,
					"Status": "active",
				}
			)
			writer.writerow(row)

		return sio.getvalue()

	def to_shopify_api_payload(self, products: list[Product]) -> list[dict]:
		payloads = []
		for p in products:
			payloads.append(
				{
					"product": {
						"title": p.title,
						"body_html": p.description,
						"vendor": "IsraelMarket.shop",
						"tags": ", ".join(p.tags),
						"product_type": p.category,
						"variants": [
							{
								"price": p.price,
								"sku": p.sku,
								"barcode": p.barcode,
								"inventory_quantity": p.stock,
							}
						],
						"images": [{"src": img} for img in ([p.image] + p.gallery if p.image else p.gallery)],
					}
				}
			)
		return payloads
