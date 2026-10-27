from functools import lru_cache
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LG_", env_file=".env", extra="ignore")
    data_dir: Path = Path("runtime")
    corpus_dir: Path = Path("data")
    prompt_dir: Path = Path("prompts")
    prompt_version: str = "v2"
    provider_mode: str = "stub"
    provider_url: str = ""
    provider_model: str = ""
    provider_api_key: str = ""
    provider_timeout_s: float = Field(8, gt=0, le=60)
    provider_retries: int = Field(2, ge=0, le=4)
    provider_failure_threshold: int = Field(3, ge=1)
    provider_cooldown_s: float = Field(20, gt=0)
    prompt_cost_per_million: float = Field(0, ge=0)
    completion_cost_per_million: float = Field(0, ge=0)
    max_steps: int = Field(24, ge=4, le=40)
    max_tool_calls: int = Field(12, ge=3, le=30)
    run_timeout_s: float = Field(45, gt=0, le=300)
    tool_timeout_s: float = Field(5, gt=0, le=20)
    lease_s: float = Field(90, gt=1)
    max_job_attempts: int = Field(2, ge=1, le=4)
    rate_limit_per_minute: int = Field(30, ge=1)
    cache_enabled: bool = True
    cache_ttl_s: int = Field(3600, ge=0)
    quality_sample_rate: float = Field(0.25, ge=0, le=1)
    metrics_port: int = 9101
    otel_endpoint: str = ""
    stub_delay_s: float = Field(0.35, ge=0, le=10)
    enable_faults: bool = False
    max_body_bytes: int = 65536

    @property
    def db_path(self) -> Path:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        return self.data_dir / "labelguard.sqlite3"


@lru_cache
def settings() -> Settings:
    return Settings()
