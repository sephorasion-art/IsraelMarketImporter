from __future__ import annotations

import re

from deep_translator import GoogleTranslator


class Translator:
	def __init__(self, source: str = "auto", target: str = "fr") -> None:
		self._translator = GoogleTranslator(source=source, target=target)
		self._cache: dict[str, str] = {}

	def _clean(self, text: str) -> str:
		return re.sub(r"\s+", " ", (text or "").strip())

	def translate(self, text: str) -> str:
		text = self._clean(text)
		if not text:
			return ""
		if text in self._cache:
			return self._cache[text]
		try:
			translated = self._translator.translate(text)
			if translated:
				self._cache[text] = translated
				return translated
		except Exception:
			return text
		return text
