import asyncio
import base64
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.v2.pipeline import run_v2_pipeline

FIXTURE_DIR = Path(__file__).parents[1] / "fixtures" / "golden"
EXPECTATIONS = json.loads((FIXTURE_DIR / "expectations.json").read_text())


def _payload_for_fixture(name: str) -> dict:
    txt = (FIXTURE_DIR / f"{name}.txt").read_text()
    return {
        "fileBase64": base64.b64encode(txt.encode("utf-8")).decode("utf-8"),
        "fileName": f"{name}.txt",
        "mimeType": "text/plain",
        "targetRole": "Senior Backend Engineer",
        "intakeData": {"email": "candidate@example.com", "phone": "+919999999999"},
    }


def test_v2_endpoint_basic_contract_shape():
    client = TestClient(app)
    payload = _payload_for_fixture("senior")
    response = client.post("/svc/resume-parser/v2/analyze", json=payload)
    assert response.status_code == 200
    body = response.json()

    assert body["version"] == "2.0"
    assert body["target_role"] == "Senior Backend Engineer"
    assert "canonical" in body and "signals" in body and "score" in body
    assert isinstance(body["recommendations"], list)
    assert isinstance(body["interview_prep"], list)
    assert "telemetry" in body and "step_durations" in body["telemetry"]


@pytest.mark.parametrize("fixture_name,expected", sorted(EXPECTATIONS.items()))
def test_golden_eval_pack_assertions(fixture_name, expected):
    payload = _payload_for_fixture(fixture_name)
    result = asyncio.run(run_v2_pipeline(payload))

    score = result["score"]["overall"]
    assert expected["score_min"] <= score <= expected["score_max"]
    assert len(result["canonical"]["experience"]) == expected["roles_count"]

    flags = {f["type"] for f in result["signals"]["red_flags"]["flags"]}
    for required_flag in expected["required_flags"]:
        assert required_flag in flags

    rec_dims = [r["dimension"] for r in result["recommendations"]]
    if expected.get("top_recommendation_dimension"):
        assert rec_dims
        assert expected["top_recommendation_dimension"] in rec_dims
