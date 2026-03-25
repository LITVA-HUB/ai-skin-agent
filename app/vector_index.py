from __future__ import annotations

import hashlib
import math
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from typing import Iterable

from .catalog import load_catalog
from .models import CatalogProduct, ProductCategory
from .text_normalization import normalize_text, tokenize


@dataclass(slots=True)
class LocalVectorHit:
    sku: str
    score: float
    vector_score: float
    lexical_score: float


@dataclass(slots=True)
class LocalVectorDocument:
    sku: str
    category: ProductCategory
    text: str
    weighted_text: str
    vector: tuple[float, ...]
    token_counts: Counter[str]


FIELD_WEIGHTS = {
    "title": 3.0,
    "brand": 1.1,
    "category": 2.4,
    "domain": 1.3,
    "skin_types": 1.6,
    "concerns": 2.0,
    "tags": 1.8,
    "ingredients": 1.0,
    "tones": 2.0,
    "undertones": 2.2,
    "finishes": 1.9,
    "coverage_levels": 1.9,
    "suitable_areas": 1.6,
    "texture": 1.1,
    "embedding_text": 1.5,
    "keywords": 1.6,
}


def stable_bucket(token: str, salt: str, dims: int) -> int:
    digest = hashlib.sha256(f"{salt}:{token}".encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % dims


def hashed_vector(tokens: Iterable[str], dims: int = 128) -> list[float]:
    counts = Counter(tokens)
    vector = [0.0] * dims
    for token, freq in counts.items():
        base_weight = 1.0 + min(freq - 1, 3) * 0.2 + min(len(token), 12) * 0.03
        idx = stable_bucket(token, "idx", dims)
        sign = -1.0 if (stable_bucket(token, "sign", 2) % 2) else 1.0
        vector[idx] += sign * base_weight
        if len(token) >= 4:
            vector[stable_bucket(token[:4], "prefix", dims)] += base_weight * 0.35
            vector[stable_bucket(token[-4:], "suffix", dims)] += base_weight * 0.2
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


@lru_cache(maxsize=2048)
def vectorize_text(text: str, dims: int = 128) -> tuple[float, ...]:
    return tuple(hashed_vector(tokenize(text), dims=dims))


def cosine_similarity(left: Iterable[float], right: Iterable[float]) -> float:
    raw = sum(a * b for a, b in zip(left, right))
    return max(0.0, min(1.0, raw))


def weighted_chunks(label: str, values: Iterable[str] | str, weight: float) -> list[str]:
    if isinstance(values, str):
        items = [values]
    else:
        items = [value for value in values if value]
    repeated = max(1, round(weight))
    chunks: list[str] = []
    for item in items:
        normalized = normalize_text(item)
        if not normalized:
            continue
        chunks.extend([normalized] * repeated)
        chunks.append(f"{label} {normalized}")
    return chunks


class LocalVectorIndex:
    def __init__(self, documents: dict[str, LocalVectorDocument]) -> None:
        self.documents = documents

    @classmethod
    def from_products(cls, products: list[CatalogProduct], build_document) -> "LocalVectorIndex":
        docs: dict[str, LocalVectorDocument] = {}
        for product in products:
            text = build_document(product)
            docs[product.sku] = LocalVectorDocument(
                sku=product.sku,
                category=product.category,
                text=text,
                weighted_text=text,
                vector=vectorize_text(text),
                token_counts=Counter(tokenize(text)),
            )
        return cls(docs)

    def lexical_score(self, query_tokens: tuple[str, ...], document: LocalVectorDocument) -> float:
        if not query_tokens:
            return 0.0
        query_counts = Counter(query_tokens)
        overlap = 0.0
        coverage = 0.0
        for token, freq in query_counts.items():
            doc_freq = document.token_counts.get(token, 0)
            if doc_freq:
                overlap += min(freq, doc_freq)
                coverage += 1.0
        overlap_ratio = overlap / max(sum(query_counts.values()), 1)
        coverage_ratio = coverage / max(len(query_counts), 1)
        return min(1.0, overlap_ratio * 0.7 + coverage_ratio * 0.3)

    def search(self, category: ProductCategory, candidates: list[CatalogProduct], query_text: str, top_k: int = 8) -> list[LocalVectorHit]:
        query_vector = vectorize_text(query_text)
        query_tokens = tokenize(query_text)
        scored: list[LocalVectorHit] = []
        for product in candidates:
            document = self.documents[product.sku]
            vector_score = cosine_similarity(query_vector, document.vector)
            lexical_score = self.lexical_score(query_tokens, document)
            category_bonus = 0.05 if product.category == category else 0.0
            score = round(min(1.0, vector_score * 0.72 + lexical_score * 0.23 + category_bonus), 4)
            scored.append(LocalVectorHit(
                sku=product.sku,
                score=score,
                vector_score=round(vector_score, 4),
                lexical_score=round(lexical_score, 4),
            ))
        scored.sort(key=lambda item: (item.score, item.vector_score, item.lexical_score), reverse=True)
        expanded_top_k = min(max(top_k * 2, 8), len(scored))
        return scored[:expanded_top_k]


@lru_cache(maxsize=256)
def cached_vector_index(build_document) -> LocalVectorIndex:
    return LocalVectorIndex.from_products(load_catalog(), build_document)
