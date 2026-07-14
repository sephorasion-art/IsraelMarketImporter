from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse

import requests


class ImageDownloader:
	def __init__(self, out_dir: str = "downloads/images") -> None:
		self.out_dir = Path(out_dir)
		self.out_dir.mkdir(parents=True, exist_ok=True)

	def download(self, url: str, filename_prefix: str = "img") -> str | None:
		if not url or not url.startswith(("http://", "https://")):
			return None
		try:
			response = requests.get(url, timeout=20)
			response.raise_for_status()
			ext = os.path.splitext(urlparse(url).path)[1] or ".jpg"
			filename = f"{filename_prefix}{ext}"
			path = self.out_dir / filename
			path.write_bytes(response.content)
			return str(path)
		except Exception:
			return None
