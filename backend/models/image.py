from dataclasses import dataclass
from typing import Optional


@dataclass
class Image:
    url: str
    alt: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
