from dataclasses import dataclass, field
from typing import List


@dataclass
class Product:
    title: str = ""
    description: str = ""
    price: float = 0.0
    compare_at_price: float = 0.0

    sku: str = ""
    barcode: str = ""
    brand: str = ""
    category: str = ""

    image: str = ""
    gallery: List[str] = field(default_factory=list)

    stock: int = 0
    weight: float = 0.0

    tags: List[str] = field(default_factory=list)

    url: str = ""