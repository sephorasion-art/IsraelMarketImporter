from __future__ import annotations

import re


class PricingEngine:
	def __init__(self, ils_to_eur: float = 0.25) -> None:
		self.ils_to_eur = ils_to_eur

	def parse_price(self, value: str | float | int | None) -> float | None:
		if value is None:
			return None
		if isinstance(value, (int, float)):
			return float(value)
		s = str(value).strip()
		s = re.sub(r"[^0-9,\.]+", "", s)
		s = s.replace(",", ".")
		try:
			return float(s)
		except Exception:
			return None

	def to_eur(self, price_ils: float | None) -> float | None:
		if price_ils is None:
			return None
		return round(price_ils * self.ils_to_eur, 2)
