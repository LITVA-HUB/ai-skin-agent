from __future__ import annotations

from .models import (
    AnalyzePhotoRequest,
    ColorFamily,
    ComplexionProfile,
    CoverageLevel,
    FinishType,
    MakeupProfile,
    MakeupStyle,
    OccasionType,
    PhotoAnalysisResult,
    PhotoSignals,
    SkinProfile,
    SkinTone,
    SkinType,
    Undertone,
    UserContext,
)


def mock_photo_analysis(request: AnalyzePhotoRequest) -> PhotoAnalysisResult:
    seed = (request.image_url or "") + (request.photo_b64 or "") + (request.user_context.goal or "")
    score = sum(ord(ch) for ch in seed) % 100 if seed else 42
    redness = round(min(1.0, 0.3 + (score % 30) / 100), 2)
    breakouts = round(min(1.0, 0.2 + ((score * 3) % 40) / 100), 2)
    oiliness = round(min(1.0, 0.25 + ((score * 5) % 35) / 100), 2)
    dryness = round(max(0.0, 0.55 - oiliness / 2), 2)
    sensitivity = round(min(1.0, redness * 0.7), 2)
    tone_cycle = [SkinTone.fair, SkinTone.light, SkinTone.light_medium, SkinTone.medium, SkinTone.tan, SkinTone.deep]
    undertone_cycle = [Undertone.neutral, Undertone.warm, Undertone.cool, Undertone.olive]
    return PhotoAnalysisResult(
        signals=PhotoSignals(
            oiliness=oiliness,
            dryness=dryness,
            redness=redness,
            breakouts=breakouts,
            tone_evenness=round(max(0.0, 1 - redness), 2),
            sensitivity_signs=sensitivity,
        ),
        complexion={
            "skin_tone": tone_cycle[score % len(tone_cycle)],
            "undertone": undertone_cycle[(score // 7) % len(undertone_cycle)],
            "under_eye_darkness": round(min(1.0, 0.15 + ((score * 2) % 35) / 100), 2),
            "visible_shine": oiliness,
            "texture_visibility": round(min(1.0, 0.2 + ((score * 4) % 30) / 100), 2),
        },
        confidence=0.62,
        limitations=["single-angle-only", "undertone-is-an-approximation"],
        source="mock",
    )


def infer_preferences_from_goal(goal: str | None) -> dict[str, object]:
    text = (goal or "").lower()
    finishes: list[FinishType] = []
    coverages: list[CoverageLevel] = []
    styles: list[MakeupStyle] = []
    colors: list[ColorFamily] = []
    occasion = None
    focus_features: list[str] = []

    if any(token in text for token in ["сия", "glow", "radiant", "dewy"]):
        finishes.append(FinishType.radiant)
    if any(token in text for token in ["мат", "matte"]):
        finishes.append(FinishType.matte)
    if any(token in text for token in ["natural", "естест", "натурал", "second skin", "дневн"]):
        finishes.append(FinishType.natural)
        styles.append(MakeupStyle.natural)
    if any(token in text for token in ["сатин", "satin"]):
        finishes.append(FinishType.satin)
    if any(token in text for token in ["легк", "sheer", "light coverage", "skin tint"]):
        coverages.extend([CoverageLevel.sheer, CoverageLevel.light])
    if any(token in text for token in ["средн", "medium coverage"]):
        coverages.append(CoverageLevel.medium)
    if any(token in text for token in ["плот", "full coverage"]):
        coverages.append(CoverageLevel.full)

    if any(token in text for token in ["вечер", "glam", "dramatic"]):
        styles.append(MakeupStyle.evening)
        styles.append(MakeupStyle.glam)
        occasion = OccasionType.party
    if any(token in text for token in ["каждый день", "everyday", "офис", "office"]):
        styles.append(MakeupStyle.everyday)
        occasion = occasion or OccasionType.everyday
    if any(token in text for token in ["clean girl", "clean look"]):
        styles.append(MakeupStyle.clean_girl)
    if any(token in text for token in ["soft luxury", "тихая роскошь", "дорого", "luxury"]):
        styles.append(MakeupStyle.soft_luxury)
    if any(token in text for token in ["sexy", "сексу", "соблазн", "дерзк"]):
        styles.append(MakeupStyle.sexy)
    if any(token in text for token in ["быстр", "quick", "5 minute"]):
        occasion = OccasionType.quick
    if any(token in text for token in ["нюд", "nude"]):
        colors.append(ColorFamily.nude)
    if any(token in text for token in ["роз", "pink"]):
        colors.append(ColorFamily.pink)
    if any(token in text for token in ["корал", "coral"]):
        colors.append(ColorFamily.coral)
    if any(token in text for token in ["berry", "ягод"]):
        colors.append(ColorFamily.berry)
    if any(token in text for token in ["red", "красн"]):
        colors.append(ColorFamily.red)
    if any(token in text for token in ["brown", "корич"]):
        colors.append(ColorFamily.brown)
    if any(token in text for token in ["губ", "lip"]):
        focus_features.append("lips")
    if any(token in text for token in ["глаз", "eye", "ресниц", "бров"]):
        focus_features.append("eyes")
    if any(token in text for token in ["румян", "blush", "cheek"]):
        focus_features.append("cheeks")

    return {
        "finishes": list(dict.fromkeys(finishes)),
        "coverages": list(dict.fromkeys(coverages)),
        "styles": list(dict.fromkeys(styles)),
        "colors": list(dict.fromkeys(colors)),
        "occasion": occasion,
        "focus_features": list(dict.fromkeys(focus_features)),
        "needs_under_eye_concealer": any(token in text for token in ["под глаза", "under eye", "консилер"]),
    }


def build_skin_profile(analysis: PhotoAnalysisResult, goal: str | None = None) -> SkinProfile:
    s = analysis.signals
    if s.oiliness > 0.6 and s.dryness < 0.35:
        skin_type = SkinType.oily
    elif s.dryness > 0.6 and s.oiliness < 0.35:
        skin_type = SkinType.dry
    elif s.sensitivity_signs > 0.65:
        skin_type = SkinType.sensitive
    elif 0.35 <= s.oiliness <= 0.7 and 0.2 <= s.dryness <= 0.6:
        skin_type = SkinType.combination
    else:
        skin_type = SkinType.normal

    concerns = []
    if s.redness >= 0.45:
        concerns.append("redness")
    if s.breakouts >= 0.45:
        concerns.append("breakouts")
    if s.dryness >= 0.45:
        concerns.append("dryness")
    if s.oiliness >= 0.55:
        concerns.append("oiliness")
    if not concerns:
        concerns.append("maintenance")

    inferred = infer_preferences_from_goal(goal)
    complexion = ComplexionProfile(
        skin_tone=analysis.complexion.skin_tone,
        undertone=analysis.complexion.undertone,
        preferred_finish=inferred["finishes"],
        preferred_coverage=inferred["coverages"],
        needs_under_eye_concealer=analysis.complexion.under_eye_darkness >= 0.45 or inferred["needs_under_eye_concealer"],
        complexion_constraints=[item for item, active in {
            "prefer_non_cakey": analysis.complexion.texture_visibility >= 0.45,
            "prefer_shine_control": analysis.complexion.visible_shine >= 0.55,
        }.items() if active],
    )
    makeup_profile = MakeupProfile(
        preferred_styles=inferred["styles"],
        preferred_color_families=inferred["colors"],
        occasion=inferred["occasion"],
        focus_features=inferred["focus_features"],
    )
    return SkinProfile(
        skin_type=skin_type,
        primary_concerns=concerns[:2],
        secondary_concerns=concerns[2:],
        cautions=["avoid_aggressive_actives"] if s.sensitivity_signs >= 0.45 else [],
        complexion=complexion,
        makeup_profile=makeup_profile,
        confidence_overall=round(min(analysis.confidence, 0.95), 2),
    )


def merge_context_preferences(context: UserContext, profile: SkinProfile) -> UserContext:
    merged = context.model_copy(deep=True)
    if not merged.preferred_finish:
        merged.preferred_finish = list(profile.complexion.preferred_finish)
    if not merged.preferred_coverage:
        merged.preferred_coverage = list(profile.complexion.preferred_coverage)
    if not merged.preferred_color_families:
        merged.preferred_color_families = list(profile.makeup_profile.preferred_color_families)
    if not merged.preferred_styles:
        merged.preferred_styles = list(profile.makeup_profile.preferred_styles)
    if not merged.occasion:
        merged.occasion = profile.makeup_profile.occasion
    return merged
