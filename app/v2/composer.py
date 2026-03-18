"""
Resume Composer — Deterministic template engine.
Converts canonical + enhanced data into ATS-safe output.
No LLM involved. Pure template rendering.
"""

from .types import CanonicalResume


ATS_TEMPLATE_V1 = "ats_v1"


def compose_resume(
    canonical: CanonicalResume,
    enhanced_summary: str,
    enhanced_bullets: list[list[str]],
    template: str = ATS_TEMPLATE_V1,
) -> dict:
    """Compose a complete resume from canonical + enhancements."""

    sections = []
    full_md_parts = []

    # --- Contact / Name ---
    # (extracted from canonical metadata or summary)

    # --- Summary ---
    summary = enhanced_summary or canonical.summary or ""
    if summary:
        sections.append({"type": "summary", "content": summary})
        full_md_parts.append(f"## Professional Summary\n\n{summary}\n")

    # --- Experience ---
    experience_entries = []
    for i, exp in enumerate(canonical.experience):
        bullets = enhanced_bullets[i] if i < len(enhanced_bullets) else exp.bullets
        entry = {
            "company": exp.company,
            "role": exp.title,
            "period": _format_period(exp.start_date, exp.end_date, exp.is_current),
            "location": exp.location or "",
            "bullets": bullets,
        }
        experience_entries.append(entry)

        # Markdown
        period_str = entry["period"]
        loc_str = f" | {exp.location}" if exp.location else ""
        full_md_parts.append(f"### {exp.title}")
        full_md_parts.append(f"**{exp.company}**{loc_str} | {period_str}\n")
        for b in bullets:
            full_md_parts.append(f"- {b}")
        full_md_parts.append("")

    if experience_entries:
        sections.append({"type": "experience", "entries": experience_entries})
        full_md_parts.insert(
            len(full_md_parts) - sum(len(e["bullets"]) + 3 for e in experience_entries),
            "## Experience\n"
        )

    # --- Education ---
    if canonical.education:
        edu_parts = ["## Education\n"]
        edu_entries = []
        for edu in canonical.education:
            degree_str = f"{edu.degree} in {edu.field}" if edu.degree and edu.field else (edu.degree or edu.field or "")
            period = _format_period(edu.start_date, edu.end_date)
            edu_entries.append({
                "institution": edu.institution,
                "degree": degree_str,
                "period": period,
                "gpa": edu.gpa,
            })
            edu_parts.append(f"**{edu.institution}**")
            if degree_str:
                edu_parts.append(f"{degree_str}")
            if period:
                edu_parts.append(f"{period}")
            if edu.gpa:
                edu_parts.append(f"GPA: {edu.gpa}")
            edu_parts.append("")

        sections.append({"type": "education", "entries": edu_entries})
        full_md_parts.extend(edu_parts)

    # --- Skills ---
    if canonical.skills:
        sections.append({"type": "skills", "items": canonical.skills})
        full_md_parts.append("## Skills\n")
        full_md_parts.append(", ".join(canonical.skills))
        full_md_parts.append("")

    # --- Certifications ---
    if canonical.certifications:
        cert_items = []
        full_md_parts.append("## Certifications\n")
        for cert in canonical.certifications:
            cert_items.append({
                "name": cert.name,
                "issuer": cert.issuer,
                "date": cert.date,
            })
            parts = [cert.name]
            if cert.issuer:
                parts.append(f"({cert.issuer})")
            if cert.date:
                parts.append(f"- {cert.date}")
            full_md_parts.append(f"- {' '.join(parts)}")
        full_md_parts.append("")
        sections.append({"type": "certifications", "items": cert_items})

    # --- Projects ---
    if canonical.projects:
        full_md_parts.append("## Projects\n")
        proj_entries = []
        for proj in canonical.projects:
            proj_entries.append({
                "name": proj.name,
                "description": proj.description,
                "technologies": proj.technologies,
                "url": proj.url,
            })
            full_md_parts.append(f"**{proj.name}**")
            if proj.description:
                full_md_parts.append(proj.description)
            if proj.technologies:
                full_md_parts.append(f"Technologies: {', '.join(proj.technologies)}")
            full_md_parts.append("")
        sections.append({"type": "projects", "entries": proj_entries})

    full_markdown = "\n".join(full_md_parts).strip()

    return {
        "template": template,
        "sections": sections,
        "fullMarkdown": full_markdown,
    }


def _format_period(start: str | None, end: str | None, is_current: bool = False) -> str:
    if not start and not end:
        return ""
    start_str = _format_date(start) if start else ""
    if is_current:
        end_str = "Present"
    else:
        end_str = _format_date(end) if end else ""

    if start_str and end_str:
        return f"{start_str} – {end_str}"
    return start_str or end_str


def _format_date(date_str: str) -> str:
    """Convert YYYY-MM to Month YYYY."""
    MONTHS = {
        "01": "Jan", "02": "Feb", "03": "Mar", "04": "Apr",
        "05": "May", "06": "Jun", "07": "Jul", "08": "Aug",
        "09": "Sep", "10": "Oct", "11": "Nov", "12": "Dec",
    }
    parts = date_str.split("-")
    if len(parts) == 2:
        return f"{MONTHS.get(parts[1], parts[1])} {parts[0]}"
    return date_str
