from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal, Self

from pydantic import (
    Field,
    HttpUrl,
    PositiveFloat,
    PositiveInt,
    SecretStr,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_DIR = Path(__file__).resolve().parent.parent
NonemptyString = Annotated[str, Field(min_length=1)]
Port = Annotated[int, Field(gt=0, le=65535)]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    content_dir: Path
    qdrant_url: HttpUrl
    qdrant_grpc_port: Port
    qdrant_collection: NonemptyString
    qdrant_timeout: PositiveFloat
    llm_url: HttpUrl
    llm_model: NonemptyString
    llm_api_key: SecretStr
    llm_timeout: PositiveFloat
    llm_reasoning_effort: Literal["none", "low", "medium", "high", "xhigh", "max"]
    embedding_model: NonemptyString
    embedding_device: NonemptyString
    reranker_model: NonemptyString
    reranker_device: NonemptyString
    reranker_dtype: NonemptyString
    reranker_batch_size: PositiveInt
    reranker_max_length: PositiveInt
    candidate_k: PositiveInt
    top_k: PositiveInt
    init_timeout: PositiveFloat

    @field_validator("llm_api_key")
    @classmethod
    def validate_llm_api_key(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().strip():
            raise ValueError("llm_api_key must not be empty.")
        return value

    @field_validator("content_dir")
    @classmethod
    def resolve_content_dir(cls, value: Path) -> Path:
        """Resolve corpus paths against the project, independent of the working directory."""
        return value if value.is_absolute() else PROJECT_DIR / value

    @model_validator(mode="after")
    def validate_search_limits(self) -> Self:
        if self.candidate_k < self.top_k:
            raise ValueError("candidate_k must be greater than or equal to top_k.")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
