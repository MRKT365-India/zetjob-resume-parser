from .llm import call_gemini
from .prompts import RECOMMENDATION_PROMPT
from .types import Recommendation


def _rerank_recommendations_by_score_gaps(recs: list[Recommendation], score) -> list[Recommendation]:
    """Stabilize recommendation priority by tying it to weakest score dimensions."""
    if not recs:
        return recs

    dims = getattr(score, "dimensions", {}) or {}

    def _dim_score(dim: str) -> float:
        d = dims.get(dim)
        if d is None:
            return 50.0
        try:
            return float(getattr(d, "score", 50.0))
        except Exception:
            return 50.0

    # Lower score => higher urgency. Estimated impact breaks ties.
    ranked = sorted(
        recs,
        key=lambda r: (
            _dim_score(getattr(r, "dimension", "")),
            -float(getattr(r, "estimated_score_impact", 0.0) or 0.0),
            getattr(r, "title", ""),
        ),
    )

    for i, rec in enumerate(ranked, start=1):
        rec.priority = i
    return ranked[:5]


def _fallback_recommendations(score, signals: dict) -> list[Recommendation]:
    recs: list[Recommendation] = []

    impact = signals.get("impact", [])
    if sum(1 for s in impact if getattr(s, "quantification", "") == "strong") < 3:
        recs.append(
            Recommendation(
                id="rec-impact-1",
                priority=1,
                title="Rewrite top bullets with measurable outcomes",
                dimension="impact_quality",
                effort="moderate",
                estimated_score_impact=10,
                description="Add metric + context + result to at least 5 bullets.",
                before="Responsible for API development",
                after="Built 6 partner APIs, reducing onboarding time by 32%.",
                location="experience",
            )
        )

    ownership = signals.get("ownership", [])
    if not any(getattr(o, "ownership_level", "") == "led" for o in ownership):
        recs.append(
            Recommendation(
                id="rec-ownership-1",
                priority=len(recs) + 1,
                title="Make ownership explicit in each role",
                dimension="ownership",
                effort="low",
                estimated_score_impact=7,
                description="Replace passive verbs with decision-level ownership statements.",
                location="experience",
            )
        )

    ats = signals.get("ats")
    if ats and getattr(ats, "pass_rate", 1.0) < 0.8:
        recs.append(
            Recommendation(
                id="rec-ats-1",
                priority=len(recs) + 1,
                title="Improve ATS structure",
                dimension="ats_compliance",
                effort="low",
                estimated_score_impact=6,
                description="Ensure standard headers, consistent dates, and contact metadata.",
                location="resume_header",
            )
        )

    if getattr(score, "overall", 100) < 60:
        recs.append(
            Recommendation(
                id="rec-narrative-1",
                priority=len(recs) + 1,
                title="Strengthen resume narrative",
                dimension="narrative_coherence",
                effort="moderate",
                estimated_score_impact=5,
                description="Align summary and experience bullets with target role outcomes.",
                location="summary",
            )
        )

    return _rerank_recommendations_by_score_gaps(recs, score)


async def generate_recommendations(target_role: str, canonical, signals: dict, alignment, score, model: str | None = None) -> list[Recommendation]:
    payload = {
        "target_role": target_role,
        "score": score.model_dump(),
        "alignment": alignment.model_dump() if alignment else None,
        "signals": {
            "impact": [x.model_dump() for x in signals.get("impact", [])],
            "ownership": [x.model_dump() for x in signals.get("ownership", [])],
            "ats": signals.get("ats").model_dump() if signals.get("ats") else {},
            "red_flags": signals.get("red_flags").model_dump() if signals.get("red_flags") else {},
        },
    }
    llm = await call_gemini(RECOMMENDATION_PROMPT, str(payload), model=model or "gemini-2.5-flash")
    if isinstance(llm, list):
        try:
            recs = [Recommendation.model_validate(x) for x in llm][:5]
            return _rerank_recommendations_by_score_gaps(recs, score)
        except Exception:
            pass
    return _fallback_recommendations(score, signals)
