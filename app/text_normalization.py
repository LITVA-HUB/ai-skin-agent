from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

TOKEN_RE = re.compile(r"[a-zA-Zа-яА-Я0-9_+-]+")
SYNONYM_MAP = {
    "тональник": ("foundation", "base", "complexion"),
    "тональный": ("foundation", "base"),
    "консилер": ("concealer", "under_eye"),
    "пудра": ("powder", "setting"),
    "сияющий": ("radiant", "glowy"),
    "сияние": ("radiant", "glow"),
    "матовый": ("matte", "blur"),
    "легкий": ("light", "sheer"),
    "лёгкий": ("light", "sheer"),
    "увлажнение": ("hydrating", "moisturizing"),
    "увлажняющий": ("hydrating", "moisturizing"),
    "покраснение": ("redness", "soothing"),
    "успокаивающий": ("soothing", "calming"),
    "высыпания": ("breakouts", "blemish", "acne"),
    "жирность": ("oiliness", "shine", "matte"),
    "сухость": ("dryness", "hydrating", "barrier"),
    "санскрин": ("spf", "sunscreen", "uv"),
    "умывание": ("cleanser", "cleanse"),
    "сыворотка": ("serum", "active"),
    "крем": ("moisturizer", "cream"),
    "подтон": ("undertone",),
    "тон": ("tone", "shade"),
    "lightweight": ("light", "sheer", "airy"),
    "glowy": ("radiant", "luminous"),
    "luminous": ("radiant", "glowy"),
    "dewy": ("radiant", "hydrated"),
    "sheer": ("light", "skin_tint"),
}


def normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text.lower())
    normalized = normalized.replace("ё", "е")
    normalized = normalized.replace("-", " ")
    normalized = re.sub(r"[^\w\s+а-яА-Я]", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


@lru_cache(maxsize=4096)
def tokenize(text: str) -> tuple[str, ...]:
    base_tokens = TOKEN_RE.findall(normalize_text(text))
    expanded: list[str] = []
    for token in base_tokens:
        expanded.append(token)
        expanded.extend(SYNONYM_MAP.get(token, ()))
        if len(token) >= 6:
            expanded.append(token[:4])
            expanded.append(token[-4:])
    return tuple(expanded)
