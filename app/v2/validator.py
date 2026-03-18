"""
Validation Layer — Post-rewrite quality checks.
Deterministic rules, no LLM.
"""

from .types import CanonicalResume


class ValidationIssue:
    def __init__(self, rule: str, severity: str, detail: str, location: str = ""):
        self.rule = rule
        self.severity = severity
        self.detail = detail
        self.location = location

    def to_dict(self):
        return {
            "rule": self.rule,
            "severity": self.severity,
            "detail": self.detail,
            "location": self.location,
        }


WEAK_PHRASES = [
    "responsible for", "worked on", "helped with", "involved in",
    "assisted with", "participated in", "was tasked with",
]

FILLER_VERBS = ["managed", "handled", "oversaw"]


def validate_rewrite(
    canonical: CanonicalResume,
    enhanced_summary: str,
    enhanced_bullets: list[list[str]],
) -> dict:
    """Run post-rewrite validation checks."""
    issues: list[ValidationIssue] = []

    # 1. Summary length check
    if enhanced_summary:
        word_count = len(enhanced_summary.split())
        if word_count > 80:
            issues.append(ValidationIssue(
                "summary_length", "medium",
                f"Summary is {word_count} words (recommended: 30-60)",
                "summary"
            ))
        elif word_count < 15:
            issues.append(ValidationIssue(
                "summary_length", "low",
                f"Summary is only {word_count} words — consider expanding",
                "summary"
            ))

    # 2. Bullet checks
    total_bullets = 0
    weak_count = 0
    long_count = 0

    for i, bullets in enumerate(enhanced_bullets):
        for j, bullet in enumerate(bullets):
            total_bullets += 1
            loc = f"experience[{i}].bullets[{j}]"

            # Weak phrase check
            lower = bullet.lower()
            for phrase in WEAK_PHRASES:
                if phrase in lower:
                    weak_count += 1
                    issues.append(ValidationIssue(
                        "weak_phrase", "medium",
                        f'Contains weak phrasing: "{phrase}"',
                        loc
                    ))
                    break

            # Length check
            words = len(bullet.split())
            if words > 30:
                long_count += 1
                issues.append(ValidationIssue(
                    "bullet_length", "low",
                    f"Bullet is {words} words (recommended: max 25)",
                    loc
                ))

            # Starts with action verb check
            if bullet and not bullet[0].isupper():
                issues.append(ValidationIssue(
                    "no_action_verb", "low",
                    "Bullet should start with a capitalized action verb",
                    loc
                ))

    # 3. Bullet count per role
    for i, bullets in enumerate(enhanced_bullets):
        if len(bullets) > 6:
            issues.append(ValidationIssue(
                "too_many_bullets", "low",
                f"Role has {len(bullets)} bullets (recommended: 3-5)",
                f"experience[{i}]"
            ))
        elif len(bullets) < 2 and i < 2:  # Only flag for top 2 roles
            issues.append(ValidationIssue(
                "too_few_bullets", "medium",
                f"Role has only {len(bullets)} bullet(s) — consider adding more",
                f"experience[{i}]"
            ))

    # 4. No hallucinated metrics check (heuristic)
    # Can't fully validate without original, but flag suspicious patterns
    for i, (orig_bullets, new_bullets) in enumerate(
        zip(
            [exp.bullets for exp in canonical.experience],
            enhanced_bullets,
        )
    ):
        for j, (orig, new) in enumerate(zip(orig_bullets, new_bullets)):
            # Count numbers in original vs new
            import re
            orig_nums = set(re.findall(r'\d+[%x]?', orig))
            new_nums = set(re.findall(r'\d+[%x]?', new))
            added_nums = new_nums - orig_nums
            # Allow ~ prefixed estimates
            if added_nums and '~' not in new:
                issues.append(ValidationIssue(
                    "possible_hallucinated_metric", "medium",
                    f"New metrics added without ~ estimate marker: {added_nums}",
                    f"experience[{i}].bullets[{j}]"
                ))

    passed = len([i for i in issues if i.severity != "low"]) == 0
    pass_rate = 1.0 - (len(issues) / max(total_bullets * 4, 1))  # normalize

    return {
        "passed": passed,
        "pass_rate": round(max(0, pass_rate), 2),
        "issue_count": len(issues),
        "issues": [i.to_dict() for i in issues],
    }
