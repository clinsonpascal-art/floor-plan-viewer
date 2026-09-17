"""End-to-end: start a generate job on the mock provider, poll to done, check
images + manifest. Run:  pytest -q   (or python tests/test_smoke.py)"""
import os
import time

os.environ.setdefault("LUXE_PROVIDER", "mock")
os.environ.setdefault("LUXE_OUT_DIR", "./renders_test")

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402
from app.config import settings  # noqa: E402

client = TestClient(app)


def test_end_to_end():
    assert client.get("/health").json()["ok"] is True

    jid = client.post("/units/residence-a/generate", data={"staged": "false"}).json()["job_id"]
    # 9 rooms on the mock provider can take >40s on a slower/shared machine
    # (measured ~46s standalone) - give this real headroom rather than a
    # tight timeout that flakes independent of any actual regression.
    for _ in range(300):
        j = client.get(f"/jobs/{jid}").json()
        if j["status"] in ("done", "error"):
            break
        time.sleep(0.2)
    assert j["status"] == "done", j.get("error")

    m = client.get("/units/residence-a/manifest").json()
    assert m["status"] == "review_required"
    assert "great" in m["rooms"] and m["rooms"]["great"]["panorama_url"]

    from pathlib import Path
    d = Path(settings.out_dir) / "residence-a"
    imgs = list(d.glob("*.jpg"))
    controls = list(d.glob("*.control.png"))
    assert len(imgs) == len(m["order"])
    assert len(controls) == len(m["order"]), "expected one control image per room"
    print(f"OK — {len(imgs)} rooms + {len(controls)} control images:", ", ".join(m["order"]))


if __name__ == "__main__":
    test_end_to_end()
