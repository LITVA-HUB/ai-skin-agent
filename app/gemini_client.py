from __future__ import annotations

import base64
import json
from typing import Any

import httpx

from .config import settings
from .models import DialogIntent, PhotoAnalysisResult


VISION_PROMPT = """
You are a strict vision parser for a Golden Apple beauty advisor.
Return only valid JSON with this exact schema:
{
  "image_check": {
    "face_detected": true,
    "skin_region_detected": true,
    "blur_score": 0.0,
    "lighting_score": 0.0,
    "makeup_possible": false,
    "usable": true
  },
  "signals": {
    "oiliness": 0.0,
    "dryness": 0.0,
    "redness": 0.0,
    "breakouts": 0.0,
    "tone_evenness": 0.0,
    "sensitivity_signs": 0.0
  },
  "complexion": {
    "skin_tone": "fair|light|light_medium|medium|tan|deep|null",
    "undertone": "cool|neutral|warm|olive|null",
    "under_eye_darkness": 0.0,
    "visible_shine": 0.0,
    "texture_visibility": 0.0
  },
  "limitations": ["string"],
  "confidence": 0.0
}
Use normalized values 0..1. Do not give product advice. Treat skin_tone and undertone as approximate only. If image quality is too poor, set usable=false.
""".strip()


class GeminiClient:
    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self.api_key = api_key or settings.gemini_api_key
        self.model = model or settings.gemini_model

    async def _generate(self, parts: list[dict[str, Any]], response_mime_type: str = "application/json") -> str | None:
        if not self.api_key:
            return None
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        payload: dict[str, Any] = {
            "generationConfig": {"temperature": 0.2, "responseMimeType": response_mime_type},
            "contents": [{"parts": parts}],
        }
        try:
            async with httpx.AsyncClient(timeout=45) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
            data = response.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except (httpx.HTTPError, KeyError, ValueError, json.JSONDecodeError):
            return None

    async def analyze_photo(self, photo_b64: str) -> PhotoAnalysisResult | None:
        mime_type = "image/jpeg"
        if photo_b64.startswith("data:"):
            header, encoded = photo_b64.split(",", 1)
            photo_b64 = encoded
            if ";base64" in header:
                mime_type = header.split(";")[0].split(":", 1)[1]
        text = await self._generate([
            {"text": VISION_PROMPT},
            {"inline_data": {"mime_type": mime_type, "data": photo_b64}},
        ])
        if not text:
            return None
        try:
            parsed = json.loads(text)
            parsed["source"] = "gemini"
            return PhotoAnalysisResult.model_validate(parsed)
        except (ValueError, json.JSONDecodeError):
            return None

    async def parse_intent(self, user_message: str, session_summary: str) -> DialogIntent | None:
        prompt = f"""
You are an intent parser for a Golden Apple beauty advisor.
Return only valid JSON with schema:
{{
  "intent": "general_advice|replace_product|cheaper_alternative|exclude_ingredient|change_brand|simplify_routine|expand_routine|explain_product|compare_products",
  "action": "recommend|replace|compare|explain|simplify|cheaper|refine",
  "domain": "skincare|makeup|hybrid",
  "target_category": "serum|moisturizer|cleanser|spf|toner|foundation|skin_tint|concealer|powder|null",
  "target_categories": ["string"],
  "target_product": null,
  "target_products": ["string"],
  "target_domain": "skincare|makeup|null",
  "preference_updates": {{
    "preferred_finish": ["natural|radiant|matte|satin"],
    "preferred_coverage": ["sheer|light|medium|full"],
    "preferred_brands": ["string"],
    "budget_direction": "cheaper|same|premium",
    "accepted_products": ["string"],
    "rejected_products": ["string"],
    "routine_size": "minimal|standard|extended"
  }},
  "constraints_update": {{
    "budget_segment": "budget|mid|premium",
    "routine_size": "minimal|standard|extended",
    "excluded_ingredients": ["string"],
    "preferred_brands": ["string"],
    "goal": "string",
    "preferred_finish": ["natural|radiant|matte|satin"],
    "preferred_coverage": ["sheer|light|medium|full"],
    "skin_tone": "fair|light|light_medium|medium|tan|deep",
    "undertone": "cool|neutral|warm|olive",
    "skin_type": "dry|oily|combination|normal|sensitive"
  }},
  "confidence": 0.0
}}
Context: {session_summary}
User message: {user_message}
Use compare_products for side-by-side requests, explain_product for "why/explain" asks, and hybrid when the user mixes skincare + complexion makeup.
Only output JSON.
""".strip()
        text = await self._generate([{"text": prompt}])
        if not text:
            return None
        try:
            return DialogIntent.model_validate(json.loads(text))
        except (ValueError, json.JSONDecodeError):
            return None

    async def generate_agent_reply(self, prompt: str) -> str | None:
        text = await self._generate([{"text": prompt}], response_mime_type="text/plain")
        return text.strip() if text else None



def is_probably_base64_image(value: str | None) -> bool:
    if not value:
        return False
    try:
        base64.b64decode(value.split(",")[-1], validate=False)
        return True
    except Exception:
        return False
