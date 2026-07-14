from dataclasses import dataclass, field
from decimal import Decimal
from typing import List, Optional

from .category import Category
from .image import Image


@dataclass
class Product:
    id: str
    title: str
    url: str
    sku: Optional[str] = None
    description: Optional[str] = None
    price: Optional[Decimal] = None
    currency: Optional[str] = None
    available: bool = True
    categories: List[Category] = field(default_factory=list)
    images: List[Image] = field(default_factory=list)
    provider: Optional[str] = None
