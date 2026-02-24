from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.config import settings
from app.schemas.api import CreateJobFromPathRequest, RunConfig
from app.services.jobs import job_manager


app = FastAPI(title=settings.app_name, version="1.0.0")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/providers/presets")
async def provider_presets() -> dict:
    return {
        "providers": [
            {
                "type": "mock",
                "description": "Local mock provider for testing without external API calls",
            },
            {
                "type": "openrouter",
                "description": "OpenRouter (OpenAI-compatible /chat/completions endpoint)",
                "required_env": ["OPENROUTER_API_KEY"],
            },
            {
                "type": "openai",
                "description": "OpenAI (chat completions endpoint)",
                "required_env": ["OPENAI_API_KEY"],
            },
            {
                "type": "openai_compatible",
                "description": "Any provider exposing OpenAI-compatible /chat/completions",
                "required_fields": ["model.base_url", "model.api_key"],
            },
        ]
    }


@app.post("/jobs/run-file")
async def run_file_job(
    file: UploadFile = File(...),
    config_json: str = Form(..., description="JSON serialized RunConfig"),
) -> dict:
    try:
        cfg = RunConfig.model_validate(json.loads(config_json))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid config_json: {exc}") from exc

    try:
        job = await job_manager.create_job_from_upload(file, cfg)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"job": job}


@app.post("/jobs/run-path")
async def run_path_job(req: CreateJobFromPathRequest) -> dict:
    try:
        job = await job_manager.create_job_from_path(req.file_path, req.config)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"job": job}


@app.get("/jobs")
async def list_jobs() -> dict:
    return {"jobs": job_manager.list_jobs()}


@app.get("/jobs/{job_id}")
async def get_job(job_id: str) -> dict:
    try:
        job = job_manager.get_job(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job": job}


@app.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: str) -> dict:
    try:
        job = await job_manager.cancel_job(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job": job}


@app.get("/jobs/{job_id}/download")
async def download_job_output(job_id: str):
    try:
        job = job_manager.get_job(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Job not found")
    if not job.output_file:
        raise HTTPException(status_code=409, detail="Job output not ready")
    path = Path(job.output_file)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Output file missing")
    return FileResponse(path, filename=path.name)

