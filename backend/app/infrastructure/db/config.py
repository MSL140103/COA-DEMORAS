from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LAYTIME_", env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://laytime:laytime_dev_pw@localhost:5432/laytime"
    storage_dir: str = "./var/storage"
    cors_origins: list[str] = ["http://localhost:3000"]


settings = Settings()
