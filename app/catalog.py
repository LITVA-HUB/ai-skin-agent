from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from .models import CatalogProduct


@lru_cache(maxsize=1)
def load_catalog() -> list[CatalogProduct]:
    path = Path(__file__).parent / "data" / "catalog.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [CatalogProduct.model_validate(item) for item in raw]
