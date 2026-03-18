from fastapi import FastAPI, HTTPException, APIRouter
from fastapi.responses import JSONResponse
from uuid import uuid4
from datetime import datetime, timezone

from .schemas import ParseRequest, ParseResponse, StatusResponse, Telemetry, RESUME_OUTPUT_SCHEMA
from .pipeline import run_pipeline
from .config import config
from .v2.types import V2AnalyzeRequest
from .v2.pipeline import run_v2_pipeline

app = FastAPI(title="resume-parser", version="0.1.0")
router = APIRouter(prefix="/svc/resume-parser")

# in-memory store (stub)
JOBS = {}
MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_BASE64_LENGTH = ((MAX_FILE_BYTES + 2) // 3) * 4

@router.post("/parse", response_model=ParseResponse)
async def parse_resume(req: ParseRequest):
    if req.file_base64 and len(req.file_base64) > MAX_BASE64_LENGTH:
        raise HTTPException(status_code=413, detail="File exceeds 5MB limit")
    job_id = str(uuid4())
    received_at = datetime.now(timezone.utc).isoformat()
    telemetry = {
        "request_id": job_id,
        "received_at": received_at,
        "pipeline_version": "0.1.1",
        "model_used": (req.models or {}).get("parse"),
    }

    result = await run_pipeline(req.model_dump())

    return ParseResponse(
        status="parsed",
        text=result.get("text"),
        scores=result.get("scores"),
        fields=result.get("fields"),
        telemetry=Telemetry(**telemetry),
    )

@router.get("/status/{id}", response_model=StatusResponse)
async def status(id: str):
    job = JOBS.get(id)
    if not job:
        raise HTTPException(status_code=404, detail="Not found")
    telemetry = Telemetry(**job.get("telemetry"))
    return StatusResponse(id=id, status=job["status"], result=job.get("result"), telemetry=telemetry)

@router.delete("/resume/{id}")
async def delete_resume(id: str):
    if id in JOBS:
        del JOBS[id]
        return JSONResponse({"deleted": True, "id": id})
    raise HTTPException(status_code=404, detail="Not found")

@router.get("/health")
async def health():
    return {"status": "ok"}

@router.get("/")
async def root():
    return {
        "service": "resume-parser",
        "env": config.env,
        "models": {
            "flash": config.gemini.model_flash,
            "pro": config.gemini.model_pro,
        },
        "stubs": {
            "ocr_provider": config.ocr.provider,
            "antivirus_provider": config.antivirus.provider,
        },
        "schema": RESUME_OUTPUT_SCHEMA,
    }

v2_router = APIRouter(prefix="/svc/resume-parser/v2")


@v2_router.post("/analyze")
async def analyze_v2(req: V2AnalyzeRequest):
    result = await run_v2_pipeline(req.model_dump(by_alias=False))
    return result


app.include_router(router)
app.include_router(v2_router)


from pydantic import BaseModel, Field as PydanticField


class V2RewriteRequest(BaseModel):
    file_base64: str = PydanticField(..., alias="fileBase64")
    file_name: str | None = PydanticField(None, alias="fileName")
    mime_type: str | None = PydanticField(None, alias="mimeType")
    target_role: str = PydanticField(..., alias="targetRole")
    intake_data: dict | None = PydanticField(None, alias="intakeData")
    models: dict[str, str] | None = None
    template: str = "ats_v1"

    model_config = {"populate_by_name": True}


@v2_router.post("/rewrite")
async def rewrite_v2(req: V2RewriteRequest):
    """Production-grade resume rewrite pipeline:
    canonicalize → extract signals → enhance bullets → compose → validate
    """
    import asyncio
    import base64
    import time

    from .pipeline import _extract_text, _is_safe_text
    from .v2.canonicalizer import canonicalize
    from .v2.extractors import extract_impact, extract_ownership, extract_skills
    from .v2.enhancer import enhance_bullets, enhance_summary
    from .v2.composer import compose_resume
    from .v2.validator import validate_rewrite

    t0 = time.perf_counter()
    models = req.models or {}
    step_durations: dict[str, int] = {}

    # 1. Ingest
    t = time.perf_counter()
    file_bytes = base64.b64decode(req.file_base64)
    text = _extract_text(file_bytes, req.mime_type, req.file_name)
    is_safe, reason = _is_safe_text(text)
    if not is_safe:
        raise HTTPException(status_code=422, detail=reason or "Unsafe content")
    step_durations["ingest"] = int((time.perf_counter() - t) * 1000)

    # 2. Canonicalize
    t = time.perf_counter()
    canonical = await canonicalize(text, model=models.get("canonicalizer"))
    step_durations["canonicalize"] = int((time.perf_counter() - t) * 1000)

    # 3. Extract signals (parallel)
    t = time.perf_counter()
    intake_data = req.intake_data or {}
    impact, ownership, skills = await asyncio.gather(
        extract_impact(canonical, model=models.get("impact"), intake_data=intake_data),
        extract_ownership(canonical, model=models.get("ownership"), intake_data=intake_data),
        extract_skills(canonical, model=models.get("skills"), intake_data=intake_data),
    )
    step_durations["extractors"] = int((time.perf_counter() - t) * 1000)

    # 4. Enhance (parallel: bullets + summary)
    t = time.perf_counter()
    enhanced_bullets, enhanced_summary = await asyncio.gather(
        enhance_bullets(
            canonical, impact, ownership, req.target_role,
            model=models.get("rewriter", "gemini-2.5-flash"),
        ),
        enhance_summary(
            canonical, req.target_role,
            model=models.get("rewriter", "gemini-2.5-flash"),
        ),
    )
    step_durations["enhance"] = int((time.perf_counter() - t) * 1000)

    # 5. Compose (deterministic)
    t = time.perf_counter()
    composed = compose_resume(canonical, enhanced_summary, enhanced_bullets, req.template)
    step_durations["compose"] = int((time.perf_counter() - t) * 1000)

    # 6. Validate
    t = time.perf_counter()
    validation = validate_rewrite(canonical, enhanced_summary, enhanced_bullets)
    step_durations["validate"] = int((time.perf_counter() - t) * 1000)

    total_ms = int((time.perf_counter() - t0) * 1000)

    return {
        "version": "2.0",
        "target_role": req.target_role,
        "rewrite": {
            "summary": enhanced_summary,
            "experience": composed["sections"][1]["entries"] if len(composed["sections"]) > 1 and composed["sections"][1].get("type") == "experience" else [],
            "skills": canonical.skills,
            "fullMarkdown": composed["fullMarkdown"],
        },
        "validation": validation,
        "original": {
            "summary": canonical.summary,
            "experience": [
                {"company": e.company, "role": e.title, "bullets": e.bullets}
                for e in canonical.experience
            ],
        },
        "telemetry": {
            "total_duration_ms": total_ms,
            "step_durations": step_durations,
        },
    }
