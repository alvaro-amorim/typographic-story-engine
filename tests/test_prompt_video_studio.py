from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from api_server.app import create_app
from engine.story_pipeline import StoryPipelineResult


def _video_runner(request, output_root, progress):
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    progress("planning", 0.1)
    progress("generating_frames", 0.7)
    (root / "preview.png").write_bytes(b"fake-png")
    (root / "result.mp4").write_bytes(b"fake-mp4")
    progress("completed", 1.0)
    return StoryPipelineResult(
        story_id="studio_story",
        root=root,
        planner_provider=request.provider,
        planner_fallback_used=False,
        frame_count=6,
        artifacts=["preview.png", "result.mp4"],
        video_path="result.mp4",
    )


def test_studio_page_capabilities_and_static_files(tmp_path: Path, monkeypatch) -> None:
    registry = tmp_path / "registry.json"
    registry.write_text("{}", encoding="utf-8")
    monkeypatch.setattr("api_server.app._resolve_executable", lambda *args: "ffmpeg")

    client = TestClient(
        create_app(
            output_root=tmp_path / "jobs",
            runner=_video_runner,
            default_registry_path=registry,
        )
    )

    assert client.get("/").status_code in {302, 307}
    studio = client.get("/studio")
    assert studio.status_code == 200
    assert "Prompt para vídeo tipográfico" in studio.text
    assert client.get("/static/studio.js").status_code == 200
    assert client.get("/static/studio.css").status_code == 200

    capabilities = client.get("/v1/capabilities").json()
    assert capabilities["ffmpeg_available"] is True
    assert capabilities["default_registry_ready"] is True
    assert set(capabilities["presets"]) == {"draft", "standard", "quality"}


def test_prompt_generation_applies_preset_and_streams_video(
    tmp_path: Path,
    monkeypatch,
) -> None:
    registry = tmp_path / "registry.json"
    registry.write_text("{}", encoding="utf-8")
    monkeypatch.setattr("api_server.app._resolve_executable", lambda *args: "ffmpeg")

    client = TestClient(
        create_app(
            output_root=tmp_path / "jobs",
            runner=_video_runner,
            default_registry_path=registry,
        )
    )
    created = client.post(
        "/v1/generations",
        json={
            "prompt": "A cat walks under the moon.",
            "preset": "draft",
            "provider": "deterministic",
            "generate_video": True,
        },
    )

    assert created.status_code == 202
    created_payload = created.json()
    job_id = created_payload["id"]
    assert created_payload["studio_url"] == f"/studio?job={job_id}"
    assert created_payload["video_url"] == f"/v1/jobs/{job_id}/video"

    job = client.get(created_payload["status_url"]).json()
    assert job["status"] == "completed"
    assert job["request"]["story"] == "A cat walks under the moon."
    assert job["request"]["duration_seconds"] == 1.0
    assert job["request"]["fps"] == 6
    assert job["request"]["video_crf"] == 28
    assert job["request"]["video_preset"] == "ultrafast"
    assert job["request"]["ffmpeg"] == "ffmpeg"

    video = client.get(f"/v1/jobs/{job_id}/video")
    assert video.status_code == 200
    assert video.content == b"fake-mp4"
    assert video.headers["content-type"].startswith("video/mp4")
    assert video.headers["content-disposition"].startswith("inline")

    preview = client.get(f"/v1/jobs/{job_id}/preview")
    assert preview.status_code == 200
    assert preview.content == b"fake-png"

    deleted = client.delete(f"/v1/jobs/{job_id}")
    assert deleted.status_code == 204
    assert client.get(f"/v1/jobs/{job_id}").status_code == 404
    assert not (tmp_path / "jobs" / job_id).exists()


def test_prompt_generation_allows_frames_without_ffmpeg(
    tmp_path: Path,
    monkeypatch,
) -> None:
    registry = tmp_path / "registry.json"
    registry.write_text("{}", encoding="utf-8")
    monkeypatch.setattr("api_server.app._resolve_executable", lambda *args: None)

    client = TestClient(
        create_app(
            output_root=tmp_path / "jobs",
            runner=_video_runner,
            default_registry_path=registry,
        )
    )

    blocked = client.post(
        "/v1/generations",
        json={"prompt": "A cat walks.", "generate_video": True},
    )
    assert blocked.status_code == 503
    assert "FFmpeg" in blocked.json()["detail"]

    frames_only = client.post(
        "/v1/generations",
        json={"prompt": "A cat walks.", "generate_video": False},
    )
    assert frames_only.status_code == 202


def test_prompt_generation_requires_default_registry(tmp_path: Path) -> None:
    client = TestClient(
        create_app(
            output_root=tmp_path / "jobs",
            runner=_video_runner,
            default_registry_path=tmp_path / "missing.json",
        )
    )

    response = client.post(
        "/v1/generations",
        json={"prompt": "A cat walks.", "generate_video": False},
    )

    assert response.status_code == 503
    assert "registry" in response.json()["detail"]
