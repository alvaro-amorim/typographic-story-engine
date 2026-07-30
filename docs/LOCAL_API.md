# Local FastAPI Service

The API exposes the complete local story pipeline as background jobs.

## Install

```powershell
python -m pip install -r requirements-dev.txt
```

## Start

```powershell
python run_api.py
```

Development reload:

```powershell
python run_api.py --reload
```

Custom output directory:

```powershell
python run_api.py `
  --host 127.0.0.1 `
  --port 8000 `
  --output-dir outputs/api-jobs
```

Interactive documentation:

```text
http://127.0.0.1:8000/docs
```

## Health

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

## Create a job

```powershell
$body = @{
  pipeline = @{
    story = "A cat looks at the moon and then walks away."
    registry_path = "C:\project\outputs\assets\asset_registry.json"
    story_id = "cat_api_01"
    provider = "deterministic"
    duration_seconds = 2
    fps = 12
    generate_png = $true
    generate_video = $false
  }
} | ConvertTo-Json -Depth 8

$job = Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/v1/jobs `
  -ContentType "application/json" `
  -Body $body
```

The endpoint returns HTTP `202`:

```json
{
  "id": "...",
  "status": "queued",
  "status_url": "/v1/jobs/..."
}
```

## Ollama job

```powershell
$body = @{
  pipeline = @{
    story = "O gato olha para a lua e caminha para a esquerda."
    registry_path = "C:\project\outputs\assets\asset_registry.json"
    provider = "ollama"
    ollama_model = "qwen3:4b"
    ollama_url = "http://localhost:11434"
    fallback_to_deterministic = $true
    duration_seconds = 2
    fps = 12
    generate_png = $true
    generate_video = $true
    video_preset = "fast"
  }
} | ConvertTo-Json -Depth 8
```

## Query status

```powershell
$status = Invoke-RestMethod `
  "http://127.0.0.1:8000$($job.status_url)"
```

Possible states:

- `queued`;
- `running`;
- `completed`;
- `failed`.

Stages include:

- `loading_registry`;
- `planning`;
- `preparing_animation`;
- `generating_frames`;
- `exporting_video`;
- `completed`.

## List jobs

```powershell
Invoke-RestMethod http://127.0.0.1:8000/v1/jobs
```

## List artifacts

```powershell
$artifacts = Invoke-RestMethod `
  "http://127.0.0.1:8000/v1/jobs/$($job.id)/artifacts"
```

## Download an artifact

```powershell
$artifact = $artifacts.artifacts[0]
Invoke-WebRequest `
  "http://127.0.0.1:8000/v1/jobs/$($job.id)/artifacts/$artifact" `
  -OutFile (Split-Path $artifact -Leaf)
```

Artifact paths are checked against the job manifest and resolved inside the job output directory. Unregistered files and path traversal attempts return `404`.

## Persistence

Each job is stored in:

```text
outputs/api-jobs/<job_id>/
├── job.json
└── artifacts/
```

The JSON record is updated atomically. If the API restarts while a job is queued or running, that job is restored as `failed` with stage `interrupted`.

## Current execution model

This MVP uses FastAPI `BackgroundTasks` in the same process.

It is appropriate for:

- local development;
- one user;
- short demonstrations;
- integration testing;
- validating the API contract.

It is not yet a distributed production queue. A later production version should move execution to a worker system such as Redis plus Dramatiq, RQ or Celery and store metadata in a database.

## Endpoints

```text
GET  /health
POST /v1/jobs
GET  /v1/jobs
GET  /v1/jobs/{job_id}
GET  /v1/jobs/{job_id}/artifacts
GET  /v1/jobs/{job_id}/artifacts/{artifact_path}
```
