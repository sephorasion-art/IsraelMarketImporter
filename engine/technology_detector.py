from __future__ import annotations

import re
from urllib.parse import urlparse


class TechnologyDetector:
    """Infer frontend technologies from URL and HTML signatures."""

    _SIGNATURES: dict[str, re.Pattern[str]] = {
        "react": re.compile(r"__react|react-dom|data-reactroot|data-reactid", re.IGNORECASE),
        "nextjs": re.compile(r"__NEXT_DATA__|_next/static|next-data", re.IGNORECASE),
        "vue": re.compile(r"__VUE__|data-v-|vue(?:\.runtime|\.global)?", re.IGNORECASE),
        "angular": re.compile(r"ng-version|angular(?:\.js|\.min)?", re.IGNORECASE),
        "alpine": re.compile(r"x-data=|alpinejs", re.IGNORECASE),
        "astro": re.compile(r"astro-island|_astro/", re.IGNORECASE),
        "nuxt": re.compile(r"__NUXT__|_nuxt/", re.IGNORECASE),
    }

    def detect(self, url: str, html: str) -> list[str]:
        technologies: set[str] = set()
        parsed = urlparse(url)
        host = parsed.netloc.lower()

        if html:
            technologies.add("html")

        for name, pattern in self._SIGNATURES.items():
            if pattern.search(html or ""):
                technologies.add(name)

        # Host-level nudges for ecosystem-specific subdomains.
        if host.endswith(".myshopify.com"):
            technologies.update({"react", "nextjs"})

        return sorted(technologies)
