import os
import time
from pathlib import Path

os.environ.setdefault("LUXE_PROVIDER", "mock")
os.environ.setdefault("LUXE_OUT_DIR", "./renders_api_test")
os.environ.setdefault("LUXE_JOB_DB", "./luxe_api_test.sqlite3")
os.environ.setdefault("LUXE_API_KEY", "test-key")

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_versioned_api_requires_key_and_runs_job():
    assert client.get("/api/v1/health").status_code == 401
    headers = {"X-API-Key": "test-key"}
    project = client.post("/api/v1/projects", headers=headers, data={"name": "API test"})
    assert project.status_code == 200
    pid = project.json()["project_id"]
    plan = Path(__file__).resolve().parents[1] / "source_continuum_residence_01.jpg"
    with plan.open("rb") as f:
        upload = client.post(f"/api/v1/projects/{pid}/floor-plan", headers=headers,
                             files={"file": (plan.name, f, "image/jpeg")})
    assert upload.status_code == 200
    input_id = upload.json()["input_id"]
    h = {**headers, "Idempotency-Key": "same-request"}
    r1 = client.post(f"/api/v1/projects/{pid}/jobs", headers=h, data={"input_id": input_id, "unit_id": "continuum-residence-01"})
    r2 = client.post(f"/api/v1/projects/{pid}/jobs", headers=h, data={"input_id": input_id, "unit_id": "continuum-residence-01"})
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json()["job_id"] == r2.json()["job_id"]
    jid = r1.json()["job_id"]
    for _ in range(300):
        status = client.get(f"/api/v1/jobs/{jid}", headers=headers).json()
        if status["status"] in {"done", "error"}:
            break
        time.sleep(0.1)
    assert status["status"] == "done", status
    assert client.get(f"/api/v1/jobs/{jid}/geometry", headers=headers).status_code == 200
    assert client.get(f"/api/v1/jobs/{jid}/rooms", headers=headers).status_code == 200
    assert client.get(f"/api/v1/jobs/{jid}/assets", headers=headers).status_code == 200
    assert client.get(f"/api/v1/jobs/{jid}/viewer", headers=headers).status_code == 200
