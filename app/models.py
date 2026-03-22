from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class SkinType(str, Enum):
    dry = "dry"
    oily = "oily"
    combination = "combination"
    normal = "normal"
    sensitive = "sensitive"


class PriceSegment(str, Enum):
    budget = "budget"
    mid = "mid"
    premium = "premium"


class BudgetDirection(str, Enum):
    cheaper = "cheaper"
    same = "same"
    premium = "premium"


class RoutineSize(str, Enum):
    minimal = "minimal"
    standard = "standard"
    extended = "extended"


class ProductDomain(str, Enum):
    skincare = "skincare"
    makeup = "makeup"


class IntentDomain(str, Enum):
    skincare = "skincare"
    makeup = "makeup"
    hybrid = "hybrid"


class IntentAction(str, Enum):
    recommend = "recommend"
    replace = "replace"
    compare = "compare"
    explain = "explain"
    simplify = "simplify"
    cheaper = "cheaper"
    refine = "refine"


class SkinTone(str, Enum):
    fair = "fair"
    light = "light"
    light_medium = "light_medium"
    medium = "medium"
    tan = "tan"
    deep = "deep"


class Undertone(str, Enum):
    cool = "cool"
    neutral = "neutral"
    warm = "warm"
    olive = "olive"


class CoverageLevel(str, Enum):
    sheer = "sheer"
    light = "light"
    medium = "medium"
    full = "full"


class FinishType(str, Enum):
    natural = "natural"
    radiant = "radiant"
    matte = "matte"
    satin = "satin"


class ImageCheck(BaseModel):
    face_detected: bool = True
    skin_region_detected: bool = True
    blur_score: float = 0.1
    lighting_score: float = 0.8
    makeup_possible: bool = False
    usable: bool = True


class PhotoSignals(BaseModel):
    oiliness: float = 0.0
    dryness: float = 0.0
    redness: float = 0.0
    breakouts: float = 0.0
    tone_evenness: float = 0.0
    sensitivity_signs: float = 0.0


class ComplexionSignals(BaseModel):
    skin_tone: SkinTone | None = None
    undertone: Undertone | None = None
    under_eye_darkness: float = 0.0
    visible_shine: float = 0.0
    texture_visibility: float = 0.0


class PhotoAnalysisResult(BaseModel):
    image_check: ImageCheck = Field(default_factory=ImageCheck)
    signals: PhotoSignals = Field(default_factory=PhotoSignals)
    complexion: ComplexionSignals = Field(default_factory=ComplexionSignals)
    limitations: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    source: str = "mock"


class ComplexionProfile(BaseModel):
    skin_tone: SkinTone | None = None
    undertone: Undertone | None = None
    preferred_finish: list[FinishType] = Field(default_factory=list)
    preferred_coverage: list[CoverageLevel] = Field(default_factory=list)
    needs_under_eye_concealer: bool = False
    complexion_constraints: list[str] = Field(default_factory=list)


class SkinProfile(BaseModel):
    skin_type: SkinType
    primary_concerns: list[str]
    secondary_concerns: list[str] = Field(default_factory=list)
    cautions: list[str] = Field(default_factory=list)
    complexion: ComplexionProfile = Field(default_factory=ComplexionProfile)
    confidence_overall: float


class UserContext(BaseModel):
    budget_segment: PriceSegment = PriceSegment.mid
    preferred_brands: list[str] = Field(default_factory=list)
    excluded_ingredients: list[str] = Field(default_factory=list)
    routine_size: RoutineSize = RoutineSize.standard
    goal: str | None = None
    budget_direction: BudgetDirection = BudgetDirection.same
    preferred_finish: list[FinishType] = Field(default_factory=list)
    preferred_coverage: list[CoverageLevel] = Field(default_factory=list)
    rejected_products: list[str] = Field(default_factory=list)
    accepted_products: list[str] = Field(default_factory=list)


class RecommendationPlan(BaseModel):
    required_categories: list[str]
    preferred_tags: list[str] = Field(default_factory=list)
    exclude_tags: list[str] = Field(default_factory=list)
    preferred_skin_types: list[str] = Field(default_factory=list)
    preferred_tones: list[str] = Field(default_factory=list)
    preferred_undertones: list[str] = Field(default_factory=list)
    preferred_finishes: list[str] = Field(default_factory=list)
    preferred_coverages: list[str] = Field(default_factory=list)
    product_domains: list[ProductDomain] = Field(default_factory=list)
    planning_notes: list[str] = Field(default_factory=list)


class CatalogProduct(BaseModel):
    sku: str
    title: str
    brand: str
    category: str
    domain: ProductDomain = ProductDomain.skincare
    price_segment: PriceSegment
    price_value: int
    availability: bool = True
    skin_types: list[str] = Field(default_factory=list)
    concerns: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    ingredients: list[str] = Field(default_factory=list)
    exclude_for: list[str] = Field(default_factory=list)
    tones: list[str] = Field(default_factory=list)
    undertones: list[str] = Field(default_factory=list)
    finishes: list[str] = Field(default_factory=list)
    coverage_levels: list[str] = Field(default_factory=list)
    suitable_areas: list[str] = Field(default_factory=list)
    texture: str | None = None
    embedding_text: str


class RecommendationItem(BaseModel):
    sku: str
    title: str
    brand: str
    category: str
    domain: ProductDomain = ProductDomain.skincare
    price_segment: PriceSegment
    price_value: int
    why: str
    vector_score: float
    rule_score: float
    final_score: float


class ConversationTurn(BaseModel):
    role: str
    message: str


class SessionState(BaseModel):
    session_id: str
    photo_analysis: PhotoAnalysisResult
    skin_profile: SkinProfile
    current_plan: RecommendationPlan
    user_preferences: UserContext
    shown_products: list[str] = Field(default_factory=list)
    rejected_products: list[str] = Field(default_factory=list)
    accepted_products: list[str] = Field(default_factory=list)
    dialog_context: dict[str, Any] = Field(default_factory=dict)
    conversation_history: list[ConversationTurn] = Field(default_factory=list)


class AnalyzePhotoRequest(BaseModel):
    photo_b64: str | None = None
    image_url: str | None = None
    user_context: UserContext = Field(default_factory=UserContext)


class AnalyzePhotoResponse(BaseModel):
    session_id: str
    photo_analysis_result: PhotoAnalysisResult
    skin_profile: SkinProfile
    recommendation_plan: RecommendationPlan
    recommendations: list[RecommendationItem]
    answer_text: str


class DialogIntent(BaseModel):
    intent: str
    action: IntentAction = IntentAction.recommend
    domain: IntentDomain = IntentDomain.skincare
    target_category: str | None = None
    target_categories: list[str] = Field(default_factory=list)
    target_product: str | None = None
    target_products: list[str] = Field(default_factory=list)
    target_domain: ProductDomain | None = None
    preference_updates: dict[str, Any] = Field(default_factory=dict)
    constraints_update: dict[str, Any] = Field(default_factory=dict)
    confidence: float = 0.0


class SessionMessageRequest(BaseModel):
    message: str


class SessionMessageResponse(BaseModel):
    intent: DialogIntent
    updated_session_state: SessionState
    recommendations: list[RecommendationItem]
    answer_text: str
