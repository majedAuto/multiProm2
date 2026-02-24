from __future__ import annotations

from typing import Any, Optional

import pandas as pd

from app.schemas.api import InstructionMode, PromptConfig, RunConfig


def row_to_mapping(row: pd.Series) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in row.to_dict().items():
        if pd.isna(value):
            out[key] = ""
        else:
            out[key] = value
    return out


def build_input_text(row: pd.Series, run_cfg: RunConfig) -> str:
    input_cfg = run_cfg.input
    row_map = row_to_mapping(row)

    if input_cfg.input_template:
        try:
            return input_cfg.input_template.format(**row_map)
        except KeyError as exc:
            raise ValueError(f"Missing column for input_template: {exc}") from exc

    parts: list[str] = []
    for col in input_cfg.input_columns:
        val = row_map.get(col, "")
        if input_cfg.include_column_labels:
            parts.append(f"{col}: {val}")
        else:
            parts.append(str(val))
    return input_cfg.input_joiner.join(parts)


def resolve_instruction(row: pd.Series, all_rows: pd.DataFrame, run_cfg: RunConfig) -> str:
    prompt_cfg = run_cfg.prompt
    mode = prompt_cfg.instruction_mode

    if mode == InstructionMode.fixed:
        return (prompt_cfg.fixed_instruction or "").strip()

    if not prompt_cfg.instruction_column:
        raise ValueError("prompt.instruction_column is required for this instruction_mode")

    current_val = row.get(prompt_cfg.instruction_column)
    current_txt = "" if pd.isna(current_val) else str(current_val).strip()

    if mode == InstructionMode.per_row:
        return current_txt

    if mode == InstructionMode.hybrid:
        fixed = (prompt_cfg.fixed_instruction or "").strip()
        return "\n".join([x for x in [fixed, current_txt] if x]).strip()

    if mode == InstructionMode.first_row_as_fixed:
        if prompt_cfg.first_row_instruction_scope_all_rows:
            first_series = all_rows[prompt_cfg.instruction_column]
        else:
            first_series = all_rows[prompt_cfg.instruction_column]
        first_non_empty = ""
        for value in first_series.tolist():
            if pd.notna(value) and str(value).strip():
                first_non_empty = str(value).strip()
                break
        return first_non_empty

    return ""


def resolve_system_prompt(row: pd.Series, run_cfg: RunConfig) -> Optional[str]:
    cfg = run_cfg.prompt
    parts: list[str] = []
    if cfg.system_prompt:
        parts.append(cfg.system_prompt)
    if cfg.system_prompt_column:
        val = row.get(cfg.system_prompt_column)
        if pd.notna(val) and str(val).strip():
            parts.append(str(val).strip())
    text = "\n".join(parts).strip()
    return text or None


def build_messages(row: pd.Series, all_rows: pd.DataFrame, run_cfg: RunConfig) -> list[dict[str, str]]:
    row_map = row_to_mapping(row)
    instruction = resolve_instruction(row, all_rows, run_cfg)
    input_text = build_input_text(row, run_cfg)
    user_template = run_cfg.prompt.user_template or "{instruction}\n\n{input}"
    user_content = user_template.format(
        instruction=instruction,
        input=input_text,
        **row_map,
    ).strip()

    messages: list[dict[str, str]] = []
    system_prompt = resolve_system_prompt(row, run_cfg)
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_content})
    return messages
