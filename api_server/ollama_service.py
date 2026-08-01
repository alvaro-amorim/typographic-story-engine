from __future__ import annotations

import json
from time import perf_counter
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


class OllamaServiceError(RuntimeError):
    """Raised when the configured Ollama service cannot answer a request."""


def normalize_ollama_url(base_url: str) -> str:
    normalized = base_url.strip().rstrip("/")
    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Ollama URL must be an absolute HTTP(S) URL")
    return normalized


def _request_json(request: Request, *, timeout_seconds: float) -> dict[str, object]:
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")
        raise OllamaServiceError(
            f"Ollama HTTP {error.code}: {details or error.reason}"
        ) from error
    except (URLError, TimeoutError, OSError) as error:
        raise OllamaServiceError(f"Ollama connection failed: {error}") from error
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise OllamaServiceError("Ollama returned invalid JSON") from error
    if not isinstance(payload, dict):
        raise OllamaServiceError("Ollama returned an unexpected response")
    return payload


def discover_ollama(
    base_url: str = "http://localhost:11434",
    *,
    timeout_seconds: float = 2.0,
) -> dict[str, object]:
    """Return Ollama version, installed models and round-trip latency."""
    if timeout_seconds <= 0.0:
        raise ValueError("Ollama timeout must be greater than zero")
    normalized = normalize_ollama_url(base_url)
    started = perf_counter()
    version_payload = _request_json(
        Request(normalized + "/api/version", method="GET"),
        timeout_seconds=timeout_seconds,
    )
    tags_payload = _request_json(
        Request(normalized + "/api/tags", method="GET"),
        timeout_seconds=timeout_seconds,
    )
    raw_models = tags_payload.get("models", [])
    if not isinstance(raw_models, list):
        raise OllamaServiceError("Ollama model list has an invalid format")

    models: list[dict[str, object]] = []
    for raw in raw_models:
        if not isinstance(raw, dict):
            continue
        details = raw.get("details") if isinstance(raw.get("details"), dict) else {}
        name = str(raw.get("name") or raw.get("model") or "").strip()
        if not name:
            continue
        models.append(
            {
                "name": name,
                "model": str(raw.get("model") or name),
                "size": int(raw.get("size") or 0),
                "modified_at": raw.get("modified_at"),
                "family": details.get("family"),
                "parameter_size": details.get("parameter_size"),
                "quantization_level": details.get("quantization_level"),
            }
        )
    models.sort(key=lambda item: str(item["name"]).lower())
    return {
        "connected": True,
        "base_url": normalized,
        "version": str(version_payload.get("version") or "unknown"),
        "latency_ms": round((perf_counter() - started) * 1000.0, 1),
        "models": models,
        "error": None,
    }


def test_ollama_model(
    model: str,
    base_url: str = "http://localhost:11434",
    *,
    timeout_seconds: float = 60.0,
) -> dict[str, object]:
    """Run a tiny non-streaming inference to verify that a model can answer."""
    selected = model.strip()
    if not selected:
        raise ValueError("Ollama model cannot be blank")
    if timeout_seconds <= 0.0:
        raise ValueError("Ollama timeout must be greater than zero")
    normalized = normalize_ollama_url(base_url)
    body = json.dumps(
        {
            "model": selected,
            "prompt": "Reply with exactly OK.",
            "stream": False,
            "keep_alive": "5m",
            "options": {"temperature": 0, "num_predict": 8},
        }
    ).encode("utf-8")
    request = Request(
        normalized + "/api/generate",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = perf_counter()
    payload = _request_json(request, timeout_seconds=timeout_seconds)
    response_text = str(payload.get("response") or "").strip()
    return {
        "connected": True,
        "base_url": normalized,
        "model": str(payload.get("model") or selected),
        "latency_ms": round((perf_counter() - started) * 1000.0, 1),
        "server_duration_ms": round(float(payload.get("total_duration") or 0) / 1_000_000.0, 1),
        "response": response_text[:200],
        "done": bool(payload.get("done", True)),
        "error": None,
    }
