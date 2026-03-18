#!/usr/bin/env python3
import asyncio
import base64
import json
from pathlib import Path

from app.v2.pipeline import run_v2_pipeline

FIXTURE_DIR = Path(__file__).parent
EXPECT = json.loads((FIXTURE_DIR / "expectations.json").read_text())

EXPECTED_FLAGS = {
    "career_gap": {"employment_gap"},
    "job_hopping": {"job_hopping", "generic_language"},
    "weak_formatting": {"stale_tech", "impact_weakness"},
    "overlapping_roles": {"overlapping_employment"},
}


def payload(name: str) -> dict:
    txt = (FIXTURE_DIR / f"{name}.txt").read_text()
    return {
        "fileBase64": base64.b64encode(txt.encode("utf-8")).decode("utf-8"),
        "fileName": f"{name}.txt",
        "mimeType": "text/plain",
        "targetRole": "Senior Backend Engineer",
        "intakeData": {"email": "candidate@example.com", "phone": "+919999999999"},
    }


def score_sanity(name: str, score: float) -> str:
    if name == "senior" and score < 70:
        return "fail"
    if name == "weak_formatting" and score > 50:
        return "fail"
    if name in {"manager", "mid_level"} and score < 60:
        return "warn"
    return "pass"


def top_recommendation_alignment(result: dict) -> str:
    recs = result["recommendations"]
    if not recs:
        return "warn"
    top_dim = recs[0]["dimension"]
    dims = result["score"]["dimensions"]
    weakest = min(dims.keys(), key=lambda k: dims[k]["score"])
    return "pass" if top_dim == weakest else f"warn ({top_dim} vs weakest {weakest})"


def red_flag_quality(name: str, flags: set[str]) -> str:
    wanted = EXPECTED_FLAGS.get(name)
    if not wanted:
        return "pass"
    hit = len(wanted & flags)
    if hit == len(wanted):
        return "pass"
    if hit > 0:
        return "warn"
    return "fail"


async def main() -> None:
    results = {}
    for fixture in sorted(EXPECT):
        results[fixture] = await run_v2_pipeline(payload(fixture))

    lines = ["# V2 Golden Fixture Quality Review", ""]
    lines.append("| fixture | score | score sanity | blockers/red-flags | rec alignment | likely FP/FN note |")
    lines.append("|---|---:|---|---|---|---|")

    for name, out in results.items():
        score = out["score"]["overall"]
        flags = {f["type"] for f in out["signals"]["red_flags"]["flags"]}
        sanity = score_sanity(name, score)
        redq = red_flag_quality(name, flags)
        recq = top_recommendation_alignment(out)

        note = ""
        if name == "overlapping_roles" and "employment_gap" in flags:
            note = "Likely FP: overlap profile flagged as gap"
        elif name == "weak_formatting" and not flags:
            note = "Likely FN: no red flags on clearly weak resume"
        elif name == "senior" and score < 75:
            note = "Potentially harsh scoring for strong senior profile"

        lines.append(f"| {name} | {score:.2f} | {sanity} | {redq} ({', '.join(sorted(flags)) or 'none'}) | {recq} | {note} |")

    out_md = FIXTURE_DIR / "QUALITY_REVIEW.md"
    out_json = FIXTURE_DIR / "quality_eval_latest.json"
    out_md.write_text("\n".join(lines) + "\n")
    out_json.write_text(json.dumps(results, indent=2))
    print(f"Wrote {out_md} and {out_json}")


if __name__ == "__main__":
    asyncio.run(main())
