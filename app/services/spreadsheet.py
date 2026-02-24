from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.schemas.api import FileType


def detect_file_type(path: Path, requested: FileType = FileType.auto) -> FileType:
    if requested != FileType.auto:
        return requested
    ext = path.suffix.lower()
    if ext == ".csv":
        return FileType.csv
    if ext in {".xlsx", ".xlsm"}:
        return FileType.xlsx
    raise ValueError(f"Unsupported file extension: {ext}")


def load_dataframe(path: Path, file_type: FileType, sheet_name: str | None = None) -> pd.DataFrame:
    if file_type == FileType.csv:
        return pd.read_csv(path)
    if file_type == FileType.xlsx:
        return pd.read_excel(path, sheet_name=sheet_name or 0, engine="openpyxl")
    raise ValueError(f"Unsupported file type: {file_type}")


def save_dataframe(df: pd.DataFrame, path: Path, file_type: FileType, sheet_name: str | None = None) -> None:
    if file_type == FileType.csv:
        df.to_csv(path, index=False)
        return
    if file_type == FileType.xlsx:
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name=sheet_name or "Sheet1")
        return
    raise ValueError(f"Unsupported file type: {file_type}")

