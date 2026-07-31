from __future__ import annotations

import json
import shutil
import threading
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from api_server.models import JobRecord
from engine.story_pipeline import StoryPipelineRequest, StoryPipelineResult


def _now() -> datetime:
    return datetime.now(timezone.utc)


class JobStore:
    """Thread-safe in-process store with one JSON record per local job."""

    def __init__(self, output_root: str | Path) -> None:
        self.output_root = Path(output_root).resolve()
        self.output_root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._jobs: dict[str, JobRecord] = {}
        self._load_existing()

    def _job_root(self, job_id: str) -> Path:
        return self.output_root / job_id

    def artifacts_root(self, job_id: str) -> Path:
        return self._job_root(job_id) / "artifacts"

    def _record_path(self, job_id: str) -> Path:
        return self._job_root(job_id) / "job.json"

    def _persist(self, record: JobRecord) -> None:
        root = self._job_root(record.id)
        root.mkdir(parents=True, exist_ok=True)
        path = self._record_path(record.id)
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(record.model_dump(mode="json"), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        temporary.replace(path)

    def _load_existing(self) -> None:
        for path in self.output_root.glob("*/job.json"):
            try:
                record = JobRecord.model_validate_json(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if record.status in {"queued", "running"}:
                record = record.model_copy(
                    update={
                        "status": "failed",
                        "stage": "interrupted",
                        "updated_at": _now(),
                        "error": "API process stopped before the job completed",
                    }
                )
                self._persist(record)
            self._jobs[record.id] = record

    def create(self, request: StoryPipelineRequest) -> JobRecord:
        with self._lock:
            job_id = uuid4().hex
            now = _now()
            record = JobRecord(
                id=job_id,
                status="queued",
                stage="queued",
                progress=0.0,
                created_at=now,
                updated_at=now,
                request=request,
            )
            self._jobs[job_id] = record
            self._persist(record)
            return record.model_copy(deep=True)

    def get(self, job_id: str) -> JobRecord | None:
        with self._lock:
            record = self._jobs.get(job_id)
            return record.model_copy(deep=True) if record is not None else None

    def list(self) -> list[JobRecord]:
        with self._lock:
            return [
                record.model_copy(deep=True)
                for record in sorted(
                    self._jobs.values(),
                    key=lambda item: item.created_at,
                    reverse=True,
                )
            ]

    def delete(self, job_id: str) -> bool:
        with self._lock:
            record = self._jobs.pop(job_id, None)
            if record is None:
                return False
            root = self._job_root(job_id).resolve()
            if root.is_relative_to(self.output_root) and root.is_dir():
                shutil.rmtree(root)
            return True

    def _update(self, job_id: str, **changes: object) -> JobRecord:
        with self._lock:
            current = self._jobs.get(job_id)
            if current is None:
                raise KeyError(job_id)
            changes["updated_at"] = _now()
            record = current.model_copy(update=changes)
            self._jobs[job_id] = record
            self._persist(record)
            return record.model_copy(deep=True)

    def mark_running(self, job_id: str) -> JobRecord:
        return self._update(
            job_id,
            status="running",
            stage="starting",
            progress=0.01,
            error=None,
        )

    def update_progress(self, job_id: str, stage: str, progress: float) -> JobRecord:
        return self._update(
            job_id,
            status="running",
            stage=stage,
            progress=max(0.0, min(0.999, float(progress))),
        )

    def complete(self, job_id: str, result: StoryPipelineResult) -> JobRecord:
        return self._update(
            job_id,
            status="completed",
            stage="completed",
            progress=1.0,
            story_id=result.story_id,
            planner_provider=result.planner_provider,
            planner_fallback_used=result.planner_fallback_used,
            frame_count=result.frame_count,
            artifacts=result.artifacts,
            video_path=result.video_path,
            error=None,
        )

    def fail(self, job_id: str, error: BaseException) -> JobRecord:
        return self._update(
            job_id,
            status="failed",
            stage="failed",
            error=f"{type(error).__name__}: {error}",
        )

    def artifact_path(self, job_id: str, relative_path: str) -> Path:
        record = self.get(job_id)
        if record is None:
            raise KeyError(job_id)
        normalized = relative_path.replace("\\", "/").lstrip("/")
        if normalized not in record.artifacts:
            raise FileNotFoundError(normalized)
        root = self.artifacts_root(job_id).resolve()
        candidate = (root / normalized).resolve()
        if not candidate.is_relative_to(root) or not candidate.is_file():
            raise FileNotFoundError(normalized)
        return candidate
