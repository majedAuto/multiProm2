from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Callable

import pandas as pd

from app.providers.base import BaseChatProvider, ChatRequest
from app.schemas.api import JobProgress, RowResult, RunConfig
from app.services.parser import parse_output_text
from app.services.prompts import build_messages


@dataclass
class ProcessedRow:
    row_result: RowResult
    split_values: dict[str, Any]
    row_updates: dict[str, Any]


class ParallelRowProcessor:
    def __init__(self, provider: BaseChatProvider, run_cfg: RunConfig) -> None:
        self.provider = provider
        self.run_cfg = run_cfg
        self.global_sem = asyncio.Semaphore(max(1, run_cfg.concurrency.global_concurrency))
        self.provider_sem = asyncio.Semaphore(max(1, run_cfg.concurrency.provider_concurrency))

    async def process_dataframe(
        self,
        df: pd.DataFrame,
        progress: JobProgress,
        cancel_event: asyncio.Event,
        on_row_done: Callable[[RowResult], None] | None = None,
    ) -> tuple[pd.DataFrame, list[RowResult]]:
        target_indices, initially_skipped = self._target_indices(df)
        progress.total_rows = len(target_indices)
        progress.queued_rows = len(target_indices)
        progress.skipped_rows = initially_skipped
        results: list[RowResult] = []

        queue: asyncio.Queue[int] = asyncio.Queue()
        for idx in target_indices:
            queue.put_nowait(idx)

        workers = [
            asyncio.create_task(
                self._worker(queue, df, progress, cancel_event, results, on_row_done),
                name=f"row-worker-{i+1}",
            )
            for i in range(max(1, self.run_cfg.concurrency.global_concurrency))
        ]

        try:
            await queue.join()
        finally:
            for _ in workers:
                queue.put_nowait(-1)
            await asyncio.gather(*workers, return_exceptions=True)

        return df, results

    def _target_indices(self, df: pd.DataFrame) -> tuple[list[int], int]:
        start = 0
        end = len(df) - 1
        if self.run_cfg.rows.start_row:
            start = max(0, self.run_cfg.rows.start_row - 2)
        if self.run_cfg.rows.end_row:
            end = min(end, self.run_cfg.rows.end_row - 2)
        if end < start:
            return [], 0

        status_col = self.run_cfg.rows.status_column
        completed_set = {s.lower() for s in self.run_cfg.rows.completed_status_values}
        indices: list[int] = []
        skipped_count = 0
        for idx in range(start, end + 1):
            if self.run_cfg.rows.skip_completed and status_col in df.columns:
                val = df.at[idx, status_col]
                if pd.notna(val) and str(val).strip().lower() in completed_set:
                    skipped_count += 1
                    continue
            indices.append(idx)
        return indices, skipped_count

    async def _worker(
        self,
        queue: asyncio.Queue[int],
        df: pd.DataFrame,
        progress: JobProgress,
        cancel_event: asyncio.Event,
        results: list[RowResult],
        on_row_done: callable | None,
    ) -> None:
        while True:
            idx = await queue.get()
            if idx == -1:
                queue.task_done()
                return

            if cancel_event.is_set():
                queue.task_done()
                continue

            progress.queued_rows = max(0, progress.queued_rows - 1)
            progress.running_rows += 1

            try:
                processed = await self._process_single(idx, df)
                self._apply_updates(df, idx, processed)
                results.append(processed.row_result)
                if processed.row_result.status.startswith("done"):
                    progress.completed_rows += 1
                elif processed.row_result.status == "skipped":
                    progress.skipped_rows += 1
                else:
                    progress.failed_rows += 1
                if on_row_done:
                    on_row_done(processed.row_result)
            finally:
                progress.running_rows = max(0, progress.running_rows - 1)
                queue.task_done()

    async def _process_single(self, idx: int, df: pd.DataFrame) -> ProcessedRow:
        row = df.iloc[idx]
        sheet_row_number = idx + 2

        try:
            messages = build_messages(row, df, self.run_cfg)
            model_name = self.run_cfg.model.model_column and str(row.get(self.run_cfg.model.model_column) or "").strip()
            model_name = model_name or self.run_cfg.model.model
            req = ChatRequest(
                model=model_name,
                messages=messages,
                temperature=self.run_cfg.model.temperature,
                max_tokens=self.run_cfg.model.max_tokens,
                top_p=self.run_cfg.model.top_p,
                timeout_seconds=self.run_cfg.model.timeout_seconds,
            )
            text = await self._chat_with_retries(req)
            split_values: dict[str, Any] = {}
            parse_error: str | None = None
            if self.run_cfg.output.split_mode.value != "none":
                try:
                    split_values = parse_output_text(text, self.run_cfg.output)
                except Exception as exc:
                    parse_error = f"Output parse error: {exc}"
                    if self.run_cfg.output.strict_parse:
                        raise

            row_updates: dict[str, Any] = {
                self.run_cfg.rows.status_column: "done" if not parse_error else "done_parse_error",
                self.run_cfg.rows.error_column: parse_error or "",
            }
            if self.run_cfg.output.write_raw_output:
                row_updates[self.run_cfg.rows.raw_output_column] = text
            row_updates.update(split_values)

            return ProcessedRow(
                row_result=RowResult(
                    index=idx,
                    sheet_row_number=sheet_row_number,
                    status=row_updates[self.run_cfg.rows.status_column],
                    error=parse_error,
                    raw_output=text if self.run_cfg.output.write_raw_output else None,
                    parsed_output=split_values or None,
                ),
                split_values=split_values,
                row_updates=row_updates,
            )
        except Exception as exc:
            err = str(exc)
            return ProcessedRow(
                row_result=RowResult(
                    index=idx,
                    sheet_row_number=sheet_row_number,
                    status="failed",
                    error=err,
                    raw_output=None,
                    parsed_output=None,
                ),
                split_values={},
                row_updates={
                    self.run_cfg.rows.status_column: "failed",
                    self.run_cfg.rows.error_column: err,
                },
            )

    async def _chat_with_retries(self, req: ChatRequest) -> str:
        attempts = max(0, self.run_cfg.model.retries) + 1
        last_exc: Exception | None = None
        for attempt in range(attempts):
            try:
                async with self.global_sem:
                    async with self.provider_sem:
                        resp = await self.provider.chat(req)
                        return resp.content.strip()
            except Exception as exc:
                last_exc = exc
                if attempt >= attempts - 1:
                    break
                await asyncio.sleep(min(5.0, 0.5 * (2**attempt)))
        assert last_exc is not None
        raise last_exc

    def _apply_updates(self, df: pd.DataFrame, idx: int, processed: ProcessedRow) -> None:
        for col, value in processed.row_updates.items():
            if col not in df.columns:
                df[col] = ""
            if (
                col in processed.split_values
                and not self.run_cfg.output.overwrite_existing_split_columns
                and pd.notna(df.at[idx, col])
                and str(df.at[idx, col]).strip()
            ):
                continue
            df.at[idx, col] = value
