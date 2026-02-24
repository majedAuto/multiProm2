from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.schemas.api import CreateJobFromPathRequest, RunConfig
from app.services.jobs import job_manager


app = FastAPI(title=settings.app_name, version="1.0.0")
ui_dir = Path(__file__).parent / "ui"
app.mount("/ui", StaticFiles(directory=ui_dir), name="ui")

_OPENROUTER_MODELS_CACHE: dict[str, Any] = {"fetched_at": 0.0, "models": []}
_OPENROUTER_MODELS_LOCK = asyncio.Lock()
_OPENROUTER_MODELS_TTL_SECONDS = 300.0


@app.get("/", include_in_schema=False)
async def index():
    return RedirectResponse(url="/ui/index.html")


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


@app.get("/providers/openrouter/models")
async def openrouter_models(force_refresh: bool = False) -> dict:
    now = time.time()
    cached_models = _OPENROUTER_MODELS_CACHE.get("models") or []
    fetched_at = float(_OPENROUTER_MODELS_CACHE.get("fetched_at") or 0.0)
    if not force_refresh and cached_models and (now - fetched_at) < _OPENROUTER_MODELS_TTL_SECONDS:
        return {
            "source": "cache",
            "count": len(cached_models),
            "fetched_at": fetched_at,
            "models": cached_models,
        }

    async with _OPENROUTER_MODELS_LOCK:
        # Recheck cache after awaiting the lock.
        now = time.time()
        cached_models = _OPENROUTER_MODELS_CACHE.get("models") or []
        fetched_at = float(_OPENROUTER_MODELS_CACHE.get("fetched_at") or 0.0)
        if not force_refresh and cached_models and (now - fetched_at) < _OPENROUTER_MODELS_TTL_SECONDS:
            return {
                "source": "cache",
                "count": len(cached_models),
                "fetched_at": fetched_at,
                "models": cached_models,
            }

        headers = {"Accept": "application/json"}
        if settings.openrouter_api_key:
            headers["Authorization"] = f"Bearer {settings.openrouter_api_key}"
        if settings.openrouter_http_referer:
            headers["HTTP-Referer"] = settings.openrouter_http_referer
        if settings.openrouter_app_title:
            headers["X-Title"] = settings.openrouter_app_title

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.get("https://openrouter.ai/api/v1/models", headers=headers)
                resp.raise_for_status()
                payload = resp.json()
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Failed to fetch OpenRouter models: {exc}") from exc

        models = _normalize_openrouter_models(payload)
        _OPENROUTER_MODELS_CACHE["models"] = models
        _OPENROUTER_MODELS_CACHE["fetched_at"] = now
        return {
            "source": "openrouter",
            "count": len(models),
            "fetched_at": now,
            "models": models,
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


def _normalize_openrouter_models(payload: dict) -> list[dict[str, Any]]:
    raw_models = payload.get("data", [])
    normalized: list[dict[str, Any]] = []

    for item in raw_models:
        if not isinstance(item, dict):
            continue
        model_id = str(item.get("id") or "").strip()
        if not model_id:
            continue
        top_provider = item.get("top_provider") or {}
        pricing = item.get("pricing") or {}
        architecture = item.get("architecture") or {}
        normalized.append(
            {
                "id": model_id,
                "name": str(item.get("name") or model_id),
                "description": str(item.get("description") or ""),
                "context_length": top_provider.get("context_length"),
                "max_completion_tokens": top_provider.get("max_completion_tokens"),
                "input_modalities": architecture.get("input_modalities") or [],
                "output_modalities": architecture.get("output_modalities") or [],
                "pricing": {
                    "prompt": pricing.get("prompt"),
                    "completion": pricing.get("completion"),
                    "request": pricing.get("request"),
                },
            }
        )

    normalized.sort(key=lambda m: (m["id"].lower(), m["name"].lower()))
    return normalized
