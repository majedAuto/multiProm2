from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator


class FileType(str, Enum):
    csv = "csv"
    xlsx = "xlsx"
    auto = "auto"


class InstructionMode(str, Enum):
    fixed = "fixed"
    per_row = "per_row"
    hybrid = "hybrid"
    first_row_as_fixed = "first_row_as_fixed"


class SplitMode(str, Enum):
    none = "none"
    json = "json"
    delimiter = "delimiter"


class ProviderType(str, Enum):
    mock = "mock"
    openai = "openai"
    openrouter = "openrouter"
    openai_compatible = "openai_compatible"


class InputConfig(BaseModel):
    input_columns: list[str] = Field(default_factory=list)
    input_template: str | None = None
    input_joiner: str = "\n"
    include_column_labels: bool = True

    @model_validator(mode="after")
    def validate_source(self) -> "InputConfig":
        if not self.input_columns and not self.input_template:
            raise ValueError("Provide input_columns or input_template")
        return self


class PromptConfig(BaseModel):
    instruction_mode: InstructionMode = InstructionMode.fixed
    fixed_instruction: str | None = None
    instruction_column: str | None = None
    system_prompt: str | None = None
    system_prompt_column: str | None = None
    user_template: str = "{instruction}\n\n{input}"
    first_row_instruction_scope_all_rows: bool = True


class ModelConfig(BaseModel):
    provider: ProviderType = ProviderType.openrouter
    model: str
    model_column: str | None = None
    api_key: str | None = None
    base_url: str | None = None
    headers: dict[str, str] = Field(default_factory=dict)
    temperature: float | None = None
    max_tokens: int | None = None
    top_p: float | None = None
    timeout_seconds: float | None = None
    retries: int = 2


class ConcurrencyConfig(BaseModel):
    global_concurrency: int = 20
    provider_concurrency: int = 10


class RowConfig(BaseModel):
    sheet_name: str | None = None
    start_row: int | None = None
    end_row: int | None = None
    status_column: str = "status"
    error_column: str = "error"
    raw_output_column: str = "output_raw"
    skip_completed: bool = True
    completed_status_values: list[str] = Field(default_factory=lambda: ["done"])


class OutputConfig(BaseModel):
    split_mode: SplitMode = SplitMode.none
    delimiter: str = "||"
    output_columns: list[str] = Field(default_factory=list)
    json_prefix: str | None = None
    strict_parse: bool = False
    write_raw_output: bool = True
    overwrite_existing_split_columns: bool = True


class RunConfig(BaseModel):
    input: InputConfig
    prompt: PromptConfig
    model: ModelConfig
    concurrency: ConcurrencyConfig = Field(default_factory=ConcurrencyConfig)
    rows: RowConfig = Field(default_factory=RowConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    metadata: dict[str, Any] = Field(default_factory=dict)


class JobState(str, Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class JobProgress(BaseModel):
    total_rows: int = 0
    queued_rows: int = 0
    running_rows: int = 0
    completed_rows: int = 0
    failed_rows: int = 0
    skipped_rows: int = 0


class RowResult(BaseModel):
    index: int
    sheet_row_number: int
    status: str
    error: str | None = None
    raw_output: str | None = None
    parsed_output: dict[str, Any] | None = None


class JobRecord(BaseModel):
    id: str
    state: JobState
    source_file: str
    output_file: str | None = None
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    config: RunConfig
    progress: JobProgress = Field(default_factory=JobProgress)
    error: str | None = None
    rows: list[RowResult] = Field(default_factory=list)


class CreateJobFromPathRequest(BaseModel):
    file_path: str
    config: RunConfig

