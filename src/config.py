"""Application configuration backed by environment variables (.env)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = Field(default="ub-rag-core")
    app_env: str = Field(default="development")
    log_level: str = Field(default="INFO")
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)

    database_url: str = Field(
        default="postgresql+asyncpg://rag:rag@localhost:5432/rag",
        description="SQLAlchemy async URL, must use postgresql+asyncpg://",
    )

    embedding_model_name: str = Field(default="BAAI/bge-m3")
    embedding_dim: int = Field(default=1024)
    reranker_model_name: str = Field(default="BAAI/bge-reranker-v2-m3")

    model_cache_dir: Path = Field(default=Path(".model_cache"))
    hf_endpoint: str | None = Field(default=None)
    device: str = Field(default="cpu", description="cpu | cuda")
    use_fp16: bool = Field(default=False)

    chunk_size: int = Field(default=512)
    chunk_overlap: int = Field(default=64)

    default_top_k: int = Field(default=20)
    default_rerank_top_k: int = Field(default=5)

    @property
    def sync_database_url(self) -> str:
        """Sync URL used by Alembic (asyncpg replaced with psycopg)."""
        url = self.database_url
        if url.startswith("postgresql+asyncpg://"):
            return url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
        return url


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
