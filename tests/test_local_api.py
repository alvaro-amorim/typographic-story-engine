from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from api_server.app import create_app
from api_server.job_store import JobStore
from engine.story_pipeline import StoryPipelineRequest, StoryPipelineResult


def _request(registry: Path) -> dict[str, object]:
    return {
        "pipeline": {
            "story": "A cat watches the moon.",
            "registry_path": str(registry),
            "story_id": "api_story",
            "generate_png": False,
            "generate_video": False,
        }
    }


def test_job_lifecycle_and_artifact_download(tmp_path: Path) -> None:
    registry = tmp_path / "registry.json"
    registry.write_text("{}", encoding="utf-8")

    def fake_runner(request, output_root, progress):
        root = Path(output_root)
        root.mkdir(parents=True, exist_ok=True)
        progress("planning", 0.1)
        progress("generating_frames", 0.6)
        (root / "result.txt").write_text("typographic-result", encoding="utf-8")
        progress("completed", 1.0)
        return StoryPipelineResult(
            story_id=request.story_id or "generated",
            root=root,
            planner_provider="deterministic",
            planner_fallback_used=False,
            frame_count=4,
            artifacts=["result.txt"],
        )

    app = create_app(output_root=tmp_path / "jobs", runner=fake_runner)
    client = TestClient(app)

    created = client.post("/v1/jobs", json=_request(registry))
    assert created.status_code == 202
    payload = created.json()
    job_id = payload["id"]
    assert payload["status"] == "queued"

    status_response = client.get(payload["status_url"])
    record = status_response.json()
    assert status_response.status_code == 200
    assert record["status"] == "completed"
    assert record["progress"] == 1.0
    assert record["stage"] == "completed"
    assert record["story_id"] == "api_story"
    assert record["frame_count"] == 4
    assert record["artifacts"] == ["result.txt"]

    artifact_list = client.get(f"/v1/jobs/{job_id}/artifacts")
    assert artifact_list.status_code == 200
    assert artifact_list.json()["artifacts"] == ["result.txt"]

    downloaded = client.get(f"/v1/jobs/{job_id}/artifacts/result.txt")
    assert downloaded.status_code == 200
    assert downloaded.text == "typographic-result"

    jobs = client.get("/v1/jobs")
    assert jobs.status_code == 200
    assert jobs.json()[0]["id"] == job_id
    assert client.get("/health").json()["status"] == "ok"


def test_failed_runner_is_recorded_instead_of_crashing_request(tmp_path: Path) -> None:
    registry = tmp_path / "registry.json"
    registry.write_text("{}", encoding="utf-8")

    def failing_runner(request, output_root, progress):
        progress("planning", 0.1)
        raise RuntimeError("planned failure")

    app = create_app(output_root=tmp_path / "jobs", runner=failing_runner)
    client = TestClient(app)
    created = client.post("/v1/jobs", json=_request(registry))
    job_id = created.json()["id"]
    record = client.get(f"/v1/jobs/{job_id}").json()

    assert created.status_code == 202
    assert record["status"] == "failed"
    assert record["stage"] == "failed"
    assert "planned failure" in record["error"]


def test_unknown_jobs_and_artifacts_return_404(tmp_path: Path) -> None:
    app = create_app(output_root=tmp_path / "jobs", runner=lambda *args: None)
    client = TestClient(app)

    assert client.get("/v1/jobs/missing").status_code == 404
    assert client.get("/v1/jobs/missing/artifacts").status_code == 404
    assert client.get("/v1/jobs/missing/artifacts/file.txt").status_code == 404


def test_artifact_endpoint_rejects_unregistered_and_traversal_paths(tmp_path: Path) -> None:
    registry = tmp_path / "registry.json"
    registry.write_text("{}", encoding="utf-8")

    def fake_runner(request, output_root, progress):
        root = Path(output_root)
        root.mkdir(parents=True, exist_ok=True)
        (root / "allowed.txt").write_text("ok", encoding="utf-8")
        return StoryPipelineResult(
            story_id="safe",
            root=root,
            planner_provider="deterministic",
            planner_fallback_used=False,
            frame_count=1,
            artifacts=["allowed.txt"],
        )

    app = create_app(output_root=tmp_path / "jobs", runner=fake_runner)
    client = TestClient(app)
    job_id = client.post("/v1/jobs", json=_request(registry)).json()["id"]

    assert client.get(f"/v1/jobs/{job_id}/artifacts/not-listed.txt").status_code == 404
    traversal = client.get(f"/v1/jobs/{job_id}/artifacts/%2E%2E/job.json")
    assert traversal.status_code == 404


def test_job_store_persists_records_and_marks_interrupted_jobs_failed(
    tmp_path: Path,
) -> None:
    root = tmp_path / "jobs"
    store = JobStore(root)
    request = StoryPipelineRequest(
        story="A cat watches the moon.",
        registry_path=tmp_path / "registry.json",
        generate_png=False,
    )
    record = store.create(request)
    store.mark_running(record.id)

    restored = JobStore(root).get(record.id)

    assert restored is not None
    assert restored.status == "failed"
    assert restored.stage == "interrupted"
    assert "stopped" in (restored.error or "")
