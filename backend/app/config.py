from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Self

from pydantic import BaseModel, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from app.tracing import traced

BASE_DIR = Path(__file__).resolve().parent.parent.parent # /etch

class AuthJWT(BaseModel):
    base_dir: Path = BASE_DIR
    private_key_path: Path
    public_key_path: Path
    algorithm: str = "RS256"
    access_token_expire_minutes: int = 5
    refresh_token_expire_days: int = 7

    @model_validator(mode="after")
    def resolve_paths(self) -> Self:
        if not self.private_key_path.is_absolute():
            self.private_key_path = self.base_dir / self.private_key_path

        if not self.public_key_path.is_absolute():
            self.public_key_path = self.base_dir / self.public_key_path

        return self


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_nested_delimiter="__",
    )
    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str
    refresh_pepper: str
    redis_user: str
    redis_password: str
    redis_name: str
    redis_port: int
    metrics_token: str
    celery_broker_url: str
    altcha_hmac_key: str
    altcha_cost: int = 5000
    altcha_min_counter: int = 500
    altcha_max_counter: int = 1000

    def database_url(self) -> str:
        return f"postgresql+asyncpg://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    def redis_url(self) -> str:
        return f"redis://{self.redis_user}:{self.redis_password}@{self.redis_name}:{self.redis_port}/0"
    

    auth_jwt: AuthJWT
    
@lru_cache
@traced("config.get_settings")
def get_settings() -> Settings:
    return Settings()

@dataclass(slots=True, frozen=True)
class AuthTokensConfig:
    private_key: str
    public_key: str
    algorithm: str
    access_token_expire_minutes: int
    refresh_token_expire_days: int
    refresh_pepper_bytes: bytes

@lru_cache
@traced("config.get_auth_tokens_config")
def get_auth_tokens_config() -> AuthTokensConfig:
    settings = get_settings()

    return AuthTokensConfig(
        private_key=settings.auth_jwt.private_key_path.read_text(encoding="utf-8"),
        public_key=settings.auth_jwt.public_key_path.read_text(encoding="utf-8"),
        algorithm=settings.auth_jwt.algorithm,
        access_token_expire_minutes=settings.auth_jwt.access_token_expire_minutes,
        refresh_token_expire_days=settings.auth_jwt.refresh_token_expire_days,
        refresh_pepper_bytes=settings.refresh_pepper.encode("utf-8"),
    )
