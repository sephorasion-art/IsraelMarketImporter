from __future__ import annotations

import re


class PriceDetector:
    """Parse and discover product prices from text snippets."""

    def parse_price(self, value: str | None) -> float | None:
        if not value:
            return None
        cleaned = re.sub(r"[^0-9,\.\-]+", "", value)
        if not cleaned:
            return None
        cleaned = cleaned.replace(" ", "")
        if "," in cleaned and "." in cleaned:
            if cleaned.rfind(",") > cleaned.rfind("."):
                cleaned = cleaned.replace(".", "")
                cleaned = cleaned.replace(",", ".")
            else:
                cleaned = cleaned.replace(",", "")
        elif "," in cleaned:
            cleaned = cleaned.replace(",", ".")
        try:
            return float(cleaned)
        except ValueError:
            return None

    def detect_in_text(self, text: str) -> float | None:
        if not text:
            return None
        for pattern in [
            r"₪\s*([0-9][0-9\.,\s]*)",
            r"([0-9][0-9\.,\s]*)\s*₪",
            r"€\s*([0-9][0-9\.,\s]*)",
            r"\$\s*([0-9][0-9\.,\s]*)",
        ]:
            match = re.search(pattern, text)
            if not match:
                continue
            parsed = self.parse_price(match.group(1))
            if parsed is not None:
                return parsed
        return self.parse_price(text)
