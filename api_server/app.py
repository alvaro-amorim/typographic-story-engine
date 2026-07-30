from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

from fastapi import BackgroundTasks, FastAPI, HTTPException, status
from fastapi.responses import FileResponse

from api_server.job_store import JobStore
from api_server.models import ArtifactList, JobCreated, JobRecord, StoryJobCreate
from engine.story_pipeline import (
    StoryPipelineRequest,
    StoryPipelineResult,
    run_story_pipeline,
)

PipelineRunner = Callable[
    [StoryPipelineRequest, str | Path, Callable[[str, float], None] | None],
    StoryPipelineResult,
]


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
) -> FastAPI:
    root = Path(
        output_root
        or os.environ.get("TSE_API_OUTPUT_ROOT", "outputs/api-jobs")
    ).resolve()
    store = JobStore(root)

    app = FastAPI(
        title="Typographic Story Engine API",
        version="0.1.0",
        description=(
            "Local job API for semantic typographic story planning, animation and video export."
        ),
    )
    app.state.job_store = store
    app.state.pipeline_runner = runner

    @app.get("/health")
    def health() -> dict[str, object]:
        return {
            "status": "ok",
            "version": app.version,
            "jobs": len(store.list()),
        }

    @app.post(
        "/v1/jobs",
        response_model=JobCreated,
        status_code=status.HTTP_202_ACCEPTED,
    )
    def create_job(
        payload: StoryJobCreate,
        background_tasks: BackgroundTasks,
    ) -> JobCreated:
        record = store.create(payload.pipeline)
        background_tasks.add_task(
            _run_job,
            store,
            record.id,
            payload.pipeline,
            runner,
        )
        return JobCreated(
            id=record.id,
            status=record.status,
            status_url=f"/v1/jobs/{record.id}",
        )

    @app.get("/v1/jobs", response_model=list[JobRecord])
    def list_jobs() -> list[JobRecord]:
        return store.list()

    @app.get("/v1/jobs/{job_id}", response_model=JobRecord)
    def get_job(job_id: str) -> JobRecord:
        record = store.get(job_id)
        if record is None:
            raise HTTPException(status_code=404, detail="job not found")
        return record

    @app.get("/v1/jobs/{job_id}/artifacts", response_model=ArtifactList)
    def list_artifacts(job_id: str) -> ArtifactList:
        record = store.get(job_id)
        if record is None:
            raise HTTPException(status_code=404, detail="job not found")
        return ArtifactList(job_id=job_id, artifacts=record.artifacts)

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
