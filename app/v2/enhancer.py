"""
Enhancement Layer — Constrained bullet-by-bullet rewriting.
No free generation. Uses signals to improve, not invent.
"""

import asyncio
from .llm import call_gemini
from .types import CanonicalResume, ImpactSignal


BULLET_REWRITE_PROMPT = """
SYSTEM:
You are a precise resume bullet editor. You IMPROVE existing text, never invent facts.

TASK:
Rewrite ONLY the provided bullets. Each rewrite must:
1. Start with a strong action verb
2. Include quantified impact IF the original has any metric hints (mark estimates with ~)
3. Be ATS-friendly (no tables, icons, special chars)
4. Preserve ALL factual claims — do NOT hallucinate
5. Remove weak phrasing: "responsible for", "worked on", "helped with", "involved in"
6. Keep under 25 words per bullet

CRITICAL: If no metric exists and none can be reasonably inferred, do NOT add fake numbers.

INPUT FORMAT:
{
  "company": "...",
  "title": "...",
  "bullets": ["original bullet 1", "original bullet 2"],
  "signals": {
    "impact_types": ["duty", "metric"],
    "weak_verbs": ["worked on"],
    "ownership_level": "led"
  }
}

OUTPUT FORMAT (JSON array, same order as input bullets):
["rewritten bullet 1", "rewritten bullet 2"]
""".strip()


SUMMARY_REWRITE_PROMPT = """
SYSTEM:
You are a resume summary specialist for the Indian job market.

TASK:
Rewrite the professional summary for the target role. Rules:
1. 2-3 sentences max
2. Lead with years of experience + core expertise
3. Include 2-3 key technologies/domains
4. End with what value the candidate brings
5. No first person ("I")
6. ATS-friendly language
7. Do NOT invent achievements — only reference what's in the resume

OUTPUT: Return ONLY the rewritten summary text (no JSON, no quotes).
""".strip()


async def enhance_bullets(
    canonical: CanonicalResume,
    impact_signals: list[ImpactSignal],
    ownership_signals: list,
    target_role: str,
    model: str = "gemini-2.5-flash",
) -> list[list[str]]:
    """Rewrite bullets role by role using signals. Returns list of bullet lists."""

    # Build signal lookup by role_index
    impact_by_role: dict[int, list[dict]] = {}
    for sig in impact_signals:
        impact_by_role.setdefault(sig.role_index, []).append({
            "bullet_index": sig.bullet_index,
            "impact_type": sig.impact_type,
            "quantification": sig.quantification,
            "weak_verbs": sig.verbs if sig.impact_type == "duty" else [],
        })

    ownership_by_role: dict[int, str] = {}
    for sig in ownership_signals:
        ownership_by_role[sig.role_index] = sig.ownership_level

    tasks = []
    for i, exp in enumerate(canonical.experience):
        if not exp.bullets:
            tasks.append(_passthrough(exp.bullets))
            continue

        signal_info = {
            "impact_types": [s["impact_type"] for s in impact_by_role.get(i, [])],
            "weak_verbs": [],
            "ownership_level": ownership_by_role.get(i, "unclear"),
        }
        for s in impact_by_role.get(i, []):
            signal_info["weak_verbs"].extend(s.get("weak_verbs", []))

        input_payload = {
            "company": exp.company,
            "title": exp.title,
            "bullets": exp.bullets,
            "signals": signal_info,
            "target_role": target_role,
        }

        import json
        tasks.append(
            call_gemini(
                BULLET_REWRITE_PROMPT,
                json.dumps(input_payload),
                model=model,
                temperature=0.3,
                max_tokens=2048,
            )
        )

    results = await asyncio.gather(*tasks)

    enhanced: list[list[str]] = []
    for i, result in enumerate(results):
        original = canonical.experience[i].bullets if i < len(canonical.experience) else []
        if isinstance(result, list) and len(result) == len(original):
            enhanced.append([str(b) for b in result])
        elif isinstance(result, list):
            # Partial result — pad with originals
            padded = [str(b) for b in result]
            padded.extend(original[len(padded):])
            enhanced.append(padded)
        else:
            enhanced.append(original)

    return enhanced


async def enhance_summary(
    canonical: CanonicalResume,
    target_role: str,
    model: str = "gemini-2.5-flash",
) -> str:
    """Rewrite the professional summary."""
    if not canonical.summary and not canonical.experience:
        return ""

    context_parts = [f"Target role: {target_role}"]
    if canonical.summary:
        context_parts.append(f"Current summary: {canonical.summary}")
    for exp in canonical.experience[:3]:
        context_parts.append(f"Experience: {exp.title} at {exp.company} ({exp.start_date} - {exp.end_date or 'Present'})")
    if canonical.skills:
        context_parts.append(f"Key skills: {', '.join(canonical.skills[:15])}")

    result = await call_gemini(
        SUMMARY_REWRITE_PROMPT,
        "\n".join(context_parts),
        model=model,
        temperature=0.4,
        max_tokens=512,
    )

    if isinstance(result, str):
        return result.strip()
    if isinstance(result, dict) and "summary" in result:
        return str(result["summary"]).strip()
    # Fallback: return original
    return canonical.summary or ""


async def _passthrough(bullets: list[str]) -> list[str]:
    return bullets
