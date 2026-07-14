from dataclasses import dataclass
from typing import Optional


@dataclass
class Category:
    id: str
    name: str
    url: Optional[str] = None
