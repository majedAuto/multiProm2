from __future__ import annotations

import asyncio
import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import UploadFile

from app.config import settings
from app.providers.factory import build_provider
from app.schemas.api import FileType, JobRecord, JobState, RunConfig
from app.services.orchestrator import ParallelRowProcessor
from app.services.spreadsheet import detect_file_type, load_dataframe, save_processed_output


class JobManager:
    def __init__(self) -> None:
        self._jobs: dict[str, JobRecord] = {}
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._cancel_events: dict[str, asyncio.Event] = {}
        self._lock = asyncio.Lock()

    def list_jobs(self) -> list[JobRecord]:
        return sorted(self._jobs.values(), key=lambda x: x.created_at, reverse=True)

    def get_job(self, job_id: str) -> JobRecord:
        job = self._jobs.get(job_id)
        if not job:
            raise KeyError(job_id)
        return job

    async def create_job_from_upload(self, file: UploadFile, config: RunConfig) -> JobRecord:
        suffix = Path(file.filename or "input.xlsx").suffix or ".xlsx"
        job_id = uuid.uuid4().hex[:12]
        source_path = settings.data_dir / f"{job_id}_input{suffix}"
        content = await file.read()
        source_path.write_bytes(content)
        return await self._create_and_start(job_id, source_path, config)

    async def create_job_from_path(self, file_path: str, config: RunConfig) -> JobRecord:
        src = Path(file_path).expanduser().resolve()
        if not src.exists():
            raise FileNotFoundError(src)
        job_id = uuid.uuid4().hex[:12]
        dest = settings.data_dir / f"{job_id}_{src.name}"
        shutil.copy2(src, dest)
        return await self._create_and_start(job_id, dest, config)

    async def cancel_job(self, job_id: str) -> JobRecord:
        if job_id not in self._jobs:
            raise KeyError(job_id)
        self._cancel_events[job_id].set()
        job = self._jobs[job_id]
        if job.state in {JobState.queued, JobState.running}:
            job.state = JobState.cancelled
            job.finished_at = _now_iso()
        return job

    async def _create_and_start(self, job_id: str, source_path: Path, config: RunConfig) -> JobRecord:
        record = JobRecord(
            id=job_id,
            state=JobState.queued,
            source_file=str(source_path),
            created_at=_now_iso(),
            config=config,
        )
        cancel_event = asyncio.Event()
        async with self._lock:
            self._jobs[job_id] = record
            self._cancel_events[job_id] = cancel_event
            self._tasks[job_id] = asyncio.create_task(self._run_job(job_id), name=f"job-{job_id}")
        return record

    async def _run_job(self, job_id: str) -> None:
        job = self._jobs[job_id]
        cancel_event = self._cancel_events[job_id]
        try:
            job.state = JobState.running
            job.started_at = _now_iso()

            source_path = Path(job.source_file)
            file_type = detect_file_type(source_path, FileType.auto)
            df = load_dataframe(source_path, file_type=file_type, sheet_name=job.config.rows.sheet_name)
            original_columns = list(df.columns)

            provider = build_provider(job.config.model)
            processor = ParallelRowProcessor(provider, job.config)

            def on_row_done(row_result):
                if len(job.rows) < 5000:
                    job.rows.append(row_result)

            df, row_results = await processor.process_dataframe(
                df=df,
                progress=job.progress,
                cancel_event=cancel_event,
                on_row_done=on_row_done,
            )

            if cancel_event.is_set() and job.state == JobState.cancelled:
                return

            if len(job.rows) == 0:
                job.rows.extend(row_results[:5000])

            out_ext = source_path.suffix.lower() if source_path.suffix.lower() in {".csv", ".xlsx"} else ".xlsx"
            output_name = _resolve_output_file_name(job_id, job.config.output.output_file_name, out_ext)
            out_file = settings.output_dir / output_name
            save_processed_output(
                df=df,
                source_path=source_path,
                output_path=out_file,
                file_type=file_type,
                source_sheet_name=job.config.rows.sheet_name,
                output_cfg=job.config.output,
                row_cfg=job.config.rows,
                original_columns=original_columns,
            )
            job.output_file = str(out_file)
            job.state = JobState.completed
            job.finished_at = _now_iso()

            meta_file = settings.output_dir / f"{job_id}_job.json"
            meta_file.write_text(
                json.dumps(job.model_dump(mode="json"), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            job.state = JobState.failed
            job.error = str(exc)
            job.finished_at = _now_iso()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve_output_file_name(job_id: str, requested_name: Optional[str], default_ext: str) -> str:
    if not requested_name:
        return f"{job_id}_output{default_ext}"
    safe_name = Path(requested_name).name.strip()
    if not safe_name:
        return f"{job_id}_output{default_ext}"
    if not Path(safe_name).suffix:
        safe_name = f"{safe_name}{default_ext}"
    return safe_name


job_manager = JobManager()
