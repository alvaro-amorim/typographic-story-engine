from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Callable

from fastapi import BackgroundTasks, FastAPI, HTTPException, Response, status
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from api_server.job_store import JobStore
from api_server.models import (
    ArtifactList,
    JobCreated,
    JobRecord,
    PromptGenerationRequest,
    StoryJobCreate,
)
from api_server.presets import PRESETS, build_pipeline_request
from engine.story_pipeline import (
    StoryPipelineRequest,
    StoryPipelineResult,
    run_story_pipeline,
)

PipelineRunner = Callable[
    [StoryPipelineRequest, str | Path, Callable[[str, float], None] | None],
    StoryPipelineResult,
]

STATIC_ROOT = Path(__file__).resolve().parent / "static"


def _resolve_executable(candidate: str | None, fallback: str) -> str | None:
    if candidate:
        explicit = Path(candidate).expanduser()
        if explicit.is_file():
            return str(explicit.resolve())
        return shutil.which(candidate)
    return shutil.which(fallback)


def _run_job(
    store: JobStore,
    job_id: str,
    request: StoryPipelineRequest,
    runner: PipelineRunner,
) -> None:
    store.mark_running(job_id)
    last_stage = ""
    last_progress = -1.0

    def progress(stage: str, value: float) -> None:
        nonlocal last_stage, last_progress
        bounded = max(0.0, min(0.999, float(value)))
        if stage != last_stage or bounded - last_progress >= 0.02:
            store.update_progress(job_id, stage, bounded)
            last_stage = stage
            last_progress = bounded

    try:
        result = runner(request, store.artifacts_root(job_id), progress)
        store.complete(job_id, result)
    except Exception as error:
        store.fail(job_id, error)


def create_app(
    *,
    output_root: str | Path | None = None,
    runner: PipelineRunner = run_story_pipeline,
    default_registry_path: str | Path | None = None,
) -> FastAPI:
    root = Path(
        output_root
        or os.environ.get("TSE_API_OUTPUT_ROOT", "outputs/api-jobs")
    ).resolve()
    configured_registry = default_registry_path or os.environ.get(
        "TSE_DEFAULT_REGISTRY_PATH"
    )
    default_registry = (
        Path(configured_registry).resolve() if configured_registry else None
    )
    store = JobStore(root)

    app = FastAPI(
        title="Typographic Story Engine API",
        version="0.3.0",
        description=(
            "Local prompt-to-video studio and job API for semantic typographic stories."
        ),
    )
    app.state.job_store = store
    app.state.pipeline_runner = runner
    app.state.default_registry_path = default_registry
    app.mount("/static", StaticFiles(directory=STATIC_ROOT), name="static")

    def enqueue(
        pipeline: StoryPipelineRequest,
        background_tasks: BackgroundTasks,
    ) -> JobCreated:
        record = store.create(pipeline)
        background_tasks.add_task(
            _run_job,
            store,
            record.id,
            pipeline,
            runner,
        )
        return JobCreated(
            id=record.id,
            status=record.status,
            status_url=f"/v1/jobs/{record.id}",
            studio_url=f"/studio?job={record.id}",
            video_url=f"/v1/jobs/{record.id}/video",
        )

    @app.get("/", include_in_schema=False)
    def index() -> RedirectResponse:
        return RedirectResponse(url="/studio")

    @app.get("/studio", include_in_schema=False)
    def studio() -> FileResponse:
        return FileResponse(STATIC_ROOT / "studio.html", media_type="text/html")

    @app.get("/health")
    def health() -> dict[str, object]:
        return {
            "status": "ok",
            "version": app.version,
            "jobs": len(store.list()),
            "studio": "/studio",
            "default_registry_ready": bool(
                default_registry and default_registry.is_file()
            ),
            "ffmpeg_available": _resolve_executable(None, "ffmpeg") is not None,
        }

    @app.get("/v1/capabilities")
    def capabilities() -> dict[str, object]:
        ffmpeg_path = _resolve_executable(None, "ffmpeg")
        return {
            "version": app.version,
            "studio_url": "/studio",
            "providers": ["deterministic", "ollama"],
            "presets": {
                name: config.as_dict() for name, config in PRESETS.items()
            },
            "ffmpeg_available": ffmpeg_path is not None,
            "ffmpeg_path": ffmpeg_path,
            "default_registry_ready": bool(
                default_registry and default_registry.is_file()
            ),
            "default_registry_path": (
                str(default_registry) if default_registry is not None else None
            ),
        }

    @app.post(
        "/v1/generations",
        response_model=JobCreated,
        status_code=status.HTTP_202_ACCEPTED,
    )
    def create_generation(
        payload: PromptGenerationRequest,
        background_tasks: BackgroundTasks,
    ) -> JobCreated:
        if default_registry is None or not default_registry.is_file():
            raise HTTPException(
                status_code=503,
                detail=(
                    "default studio registry is not ready; start with "
                    "`python -m commands.studio` or configure TSE_DEFAULT_REGISTRY_PATH"
                ),
            )

        pipeline = build_pipeline_request(payload, default_registry)
        if pipeline.generate_video:
            ffmpeg_path = _resolve_executable(pipeline.ffmpeg, "ffmpeg")
            if ffmpeg_path is None:
                raise HTTPException(
                    status_code=503,
                    detail=(
                        "FFmpeg was not found. Install it or submit with "
                        "generate_video=false to generate frames only."
                    ),
                )
            pipeline = pipeline.model_copy(update={"ffmpeg": ffmpeg_path})
        return enqueue(pipeline, background_tasks)

    @app.post(
        "/v1/jobs",
        response_model=JobCreated,
        status_code=status.HTTP_202_ACCEPTED,
    )
    def create_job(
        payload: StoryJobCreate,
        background_tasks: BackgroundTasks,
    ) -> JobCreated:
        return enqueue(payload.pipeline, background_tasks)

    @app.get("/v1/jobs", response_model=list[JobRecord])
    def list_jobs() -> list[JobRecord]:
        return store.list()

    @app.get("/v1/jobs/{job_id}", response_model=JobRecord)
    def get_job(job_id: str) -> JobRecord:
        record = store.get(job_id)
        if record is None:
            raise HTTPException(status_code=404, detail="job not found")
        return record

    @app.delete("/v1/jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_job(job_id: str) -> Response:
        if not store.delete(job_id):
            raise HTTPException(status_code=404, detail="job not found")
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @app.get("/v1/jobs/{job_id}/artifacts", response_model=ArtifactList)
    def list_artifacts(job_id: str) -> ArtifactList:
        record = store.get(job_id)
        if record is None:
            raise HTTPException(status_code=404, detail="job not found")
        return ArtifactList(job_id=job_id, artifacts=record.artifacts)

    @app.get("/v1/jobs/{job_id}/video")
    def stream_video(job_id: str) -> FileResponse:
        record = store.get(job_id)
        if record is None:
            raise HTTPException(status_code=404, detail="job not found")
        if not record.video_path:
            raise HTTPException(status_code=409, detail="video is not ready")
        try:
            path = store.artifact_path(job_id, record.video_path)
        except FileNotFoundError as error:
            raise HTTPException(status_code=404, detail="video artifact not found") from error
        return FileResponse(
            path=path,
            media_type="video/mp4",
            headers={"Content-Disposition": f'inline; filename="{path.name}"'},
        )

    @app.get("/v1/jobs/{job_id}/preview")
    def preview_frame(job_id: str) -> FileResponse:
        record = store.get(job_id)
        if record is None:
            raise HTTPException(status_code=404, detail="job not found")
        png_artifacts = [
            item for item in record.artifacts if item.lower().endswith(".png")
        ]
        if not png_artifacts:
            raise HTTPException(status_code=409, detail="preview is not ready")
        path = store.artifact_path(job_id, png_artifacts[-1])
        return FileResponse(path=path, media_type="image/png")

    @app.get("/v1/jobs/{job_id}/artifacts/{artifact_path:path}")
    def download_artifact(job_id: str, artifact_path: str) -> FileResponse:
        try:
            path = store.artifact_path(job_id, artifact_path)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="job not found") from error
        except FileNotFoundError as error:
            raise HTTPException(status_code=404, detail="artifact not found") from error
        return FileResponse(path=path, filename=path.name)

    return app


app = create_app()
