from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from api_server.app import create_app
from api_server.ollama_service import discover_ollama
from api_server.ollama_service import test_ollama_model as run_model_test
from engine.story_pipeline import StoryPipelineResult


class _FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def test_discover_ollama_reads_version_and_sorted_models(monkeypatch) -> None:
    calls: list[str] = []

    def fake_urlopen(request, timeout):
        calls.append(request.full_url)
        assert timeout == 3.0
        if request.full_url.endswith("/api/version"):
            return _FakeResponse({"version": "0.12.6"})
        return _FakeResponse(
            {
                "models": [
                    {
                        "name": "qwen3:8b",
                        "size": 8,
                        "details": {
                            "family": "qwen3",
                            "parameter_size": "8B",
                            "quantization_level": "Q4_K_M",
                        },
                    },
                    {
                        "name": "gemma3:4b",
                        "size": 4,
                        "details": {"parameter_size": "4B"},
                    },
                ]
            }
        )

    monkeypatch.setattr("api_server.ollama_service.urlopen", fake_urlopen)
    result = discover_ollama("http://localhost:11434/", timeout_seconds=3.0)

    assert calls == [
        "http://localhost:11434/api/version",
        "http://localhost:11434/api/tags",
    ]
    assert result["connected"] is True
    assert result["version"] == "0.12.6"
    assert [item["name"] for item in result["models"]] == ["gemma3:4b", "qwen3:8b"]
    assert result["models"][1]["parameter_size"] == "8B"


def test_model_test_uses_small_non_streaming_generation(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return _FakeResponse(
            {
                "model": "qwen3:4b",
                "response": "OK",
                "done": True,
                "total_duration": 125_000_000,
            }
        )

    monkeypatch.setattr("api_server.ollama_service.urlopen", fake_urlopen)
    result = run_model_test(
        "qwen3:4b",
        "http://localhost:11434",
        timeout_seconds=45.0,
    )

    assert captured["url"] == "http://localhost:11434/api/generate"
    assert captured["timeout"] == 45.0
    assert captured["payload"]["stream"] is False
    assert captured["payload"]["options"]["num_predict"] == 8
    assert result["connected"] is True
    assert result["response"] == "OK"
    assert result["server_duration_ms"] == 125.0


def _runner(request, output_root, progress):
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    progress("completed", 1.0)
    return StoryPipelineResult(
        story_id="ollama_test_story",
        root=root,
        planner_provider=request.provider,
        planner_fallback_used=False,
        frame_count=2,
        artifacts=[],
    )


def test_ollama_status_and_test_endpoints(monkeypatch, tmp_path: Path) -> None:
    registry = tmp_path / "registry.json"
    registry.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        "api_server.app.discover_ollama",
        lambda base_url, timeout_seconds: {
            "connected": True,
            "base_url": base_url,
            "version": "0.12.6",
            "latency_ms": 8.4,
            "models": [{"name": "qwen3:4b", "parameter_size": "4B"}],
            "error": None,
        },
    )
    monkeypatch.setattr(
        "api_server.app.run_ollama_model_test",
        lambda model, base_url, timeout_seconds: {
            "connected": True,
            "base_url": base_url,
            "model": model,
            "latency_ms": 321.0,
            "server_duration_ms": 300.0,
            "response": "OK",
            "done": True,
            "error": None,
        },
    )

    client = TestClient(
        create_app(
            output_root=tmp_path / "jobs",
            runner=_runner,
            default_registry_path=registry,
        )
    )
    status = client.get(
        "/v1/ollama/status",
        params={"base_url": "http://localhost:11434", "timeout_seconds": 2},
    )
    assert status.status_code == 200
    assert status.json()["models"][0]["name"] == "qwen3:4b"

    tested = client.post(
        "/v1/ollama/test",
        json={
            "base_url": "http://localhost:11434",
            "model": "qwen3:4b",
            "timeout_seconds": 60,
        },
    )
    assert tested.status_code == 200
    assert tested.json()["connected"] is True
    assert tested.json()["latency_ms"] == 321.0

    capabilities = client.get("/v1/capabilities").json()
    assert capabilities["version"] == "0.5.0"
    assert capabilities["ollama"]["model_discovery"] is True
    assert capabilities["ollama"]["fallback_supported"] is True


def test_studio_publishes_model_selector_test_button_and_styles(tmp_path: Path) -> None:
    registry = tmp_path / "registry.json"
    registry.write_text("{}", encoding="utf-8")
    client = TestClient(
        create_app(
            output_root=tmp_path / "jobs",
            runner=_runner,
            default_registry_path=registry,
        )
    )

    studio = client.get("/studio")
    assert studio.status_code == 200
    assert 'id="ollama-model"' in studio.text
    assert 'id="ollama-test"' in studio.text
    assert 'id="ollama-fallback"' in studio.text
    assert "/static/ollama-studio.css" in studio.text
    assert client.get("/static/ollama-studio.css").status_code == 200
