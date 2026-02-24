from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Parallel Spreadsheet AI"
    data_dir: Path = Path("data")
    output_dir: Path = Path("outputs")
    default_global_concurrency: int = 20
    default_provider_concurrency: int = 10
    request_timeout_seconds: float = 120.0

    openai_api_key: str | None = None
    openrouter_api_key: str | None = None
    openrouter_http_referer: str | None = None
    openrouter_app_title: str | None = None


settings = Settings()
settings.data_dir.mkdir(parents=True, exist_ok=True)
settings.output_dir.mkdir(parents=True, exist_ok=True)

