from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from app.schemas.api import OutputConfig, SplitMode


def flatten_json(value: Any, prefix: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {}
    if isinstance(value, Mapping):
        for key, inner in value.items():
            key_name = f"{prefix}.{key}" if prefix else str(key)
            out.update(flatten_json(inner, key_name))
        return out
    if isinstance(value, list):
        for i, inner in enumerate(value, start=1):
            key_name = f"{prefix}.{i}" if prefix else str(i)
            out.update(flatten_json(inner, key_name))
        return out
    if prefix:
        out[prefix] = value
    else:
        out["value"] = value
    return out


def parse_output_text(text: str, cfg: OutputConfig) -> dict[str, Any]:
    if cfg.split_mode == SplitMode.none:
        return {}

    if cfg.split_mode == SplitMode.delimiter:
        parts = [p.strip() for p in text.split(cfg.delimiter)]
        if cfg.output_columns:
            out: dict[str, Any] = {}
            for idx, col in enumerate(cfg.output_columns):
                out[col] = parts[idx] if idx < len(parts) else None
            if len(parts) > len(cfg.output_columns):
                out[f"extra_parts_count"] = len(parts) - len(cfg.output_columns)
            return out
        return {f"part_{i}": v for i, v in enumerate(parts, start=1)}

    if cfg.split_mode == SplitMode.json:
        parsed = json.loads(text)
        flat = flatten_json(parsed)
        if cfg.output_columns:
            selected: dict[str, Any] = {}
            for name in cfg.output_columns:
                selected[name] = flat.get(name)
            return selected
        if cfg.json_prefix:
            return {f"{cfg.json_prefix}{k}": v for k, v in flat.items()}
        return flat

    return {}

