from datetime import datetime

from ..llm import call_gemini
from ..prompts import RED_FLAG_DETECTOR_PROMPT
from ..types import CanonicalResume, RedFlag, RedFlagSignal




_FLAG_ALIASES = {
    "frequent_hopping": "job_hopping",
}


def _normalize_flag_types(signal: RedFlagSignal) -> RedFlagSignal:
    normalized: list[RedFlag] = []
    for flag in signal.flags:
        ftype = _FLAG_ALIASES.get(flag.type, flag.type)
        normalized.append(RedFlag(type=ftype, severity=flag.severity, detail=flag.detail, location=flag.location))
    return RedFlagSignal(flags=normalized)


def _to_dt(ym: str | None) -> datetime | None:
    if not ym or len(ym) < 7:
        return None
    try:
        return datetime.strptime(ym, "%Y-%m")
    except Exception:
        return None


def _months_between(a: datetime, b: datetime) -> int:
    return (b.year - a.year) * 12 + (b.month - a.month)


def _heuristic_red_flags(canonical: CanonicalResume) -> RedFlagSignal:
    flags: list[RedFlag] = []

    # gaps
    roles = sorted(canonical.experience, key=lambda r: r.start_date or "")
    for i in range(1, len(roles)):
        prev_end = _to_dt(roles[i - 1].end_date)
        curr_start = _to_dt(roles[i].start_date)
        if prev_end and curr_start:
            gap = _months_between(prev_end, curr_start)
            if gap > 6:
                flags.append(RedFlag(type="employment_gap", severity="medium" if gap < 12 else "high", detail=f"{gap}-month gap between roles", location=f"experience[{i}]"))

    # hopping + generic language
    short_roles = 0
    generic_hits = 0
    stale_hits = 0
    stale_tokens = {"jquery", "svn", "dreamweaver", "visual basic 6"}

    for i, role in enumerate(canonical.experience):
        start, end = _to_dt(role.start_date), _to_dt(role.end_date)
        if start and end and _months_between(start, end) < 12:
            short_roles += 1
        for j, bullet in enumerate(role.bullets):
            b = bullet.lower()
            if "responsible for" in b or "various" in b:
                generic_hits += 1
                flags.append(RedFlag(type="generic_language", severity="low", detail="Duty-heavy or generic wording", location=f"experience[{i}].bullets[{j}]"))
            if any(t in b for t in stale_tokens):
                stale_hits += 1

    if short_roles >= 3:
        flags.append(RedFlag(type="job_hopping", severity="medium", detail=f"{short_roles} roles shorter than 12 months", location="experience"))
    if stale_hits:
        flags.append(RedFlag(type="stale_tech", severity="low", detail="Potentially outdated tech emphasis", location="skills/experience"))
    if generic_hits >= 4:
        flags.append(RedFlag(type="impact_weakness", severity="medium", detail="Many bullets are duty statements without outcomes", location="experience"))

    return RedFlagSignal(flags=flags)


async def extract_red_flags(canonical: CanonicalResume, model: str | None = None, intake_data: dict | None = None) -> RedFlagSignal:
    payload = {
        "experience": [r.model_dump() for r in canonical.experience],
        "skills": canonical.skills,
    }
    llm = await call_gemini(RED_FLAG_DETECTOR_PROMPT, str(payload), model=model or "gemini-2.5-flash")
    if isinstance(llm, dict):
        try:
            return _normalize_flag_types(RedFlagSignal.model_validate(llm))
        except Exception:
            pass
    return _normalize_flag_types(_heuristic_red_flags(canonical))
