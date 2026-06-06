from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_path: Path = Path("../data/time_machine.sqlite3")
    repos_dir: Path = Path("../data/repos")
    github_token: Optional[str] = None
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-5.1"
    max_commits: int = 500
    github_fetch_limit: int = 100


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    settings.repos_dir.mkdir(parents=True, exist_ok=True)
    return settings
