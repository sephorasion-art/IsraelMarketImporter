from __future__ import annotations


class SeoGenerator:
	def build(self, title: str, description: str) -> dict[str, str]:
		title = (title or "").strip()
		description = (description or "").strip()
		if not description:
			description = f"Découvrez {title} sur IsraelMarket.shop."
		return {
			"seo_title": f"Achetez {title} en ligne | IsraelMarket.shop"[:70],
			"seo_description": description[:160],
		}
