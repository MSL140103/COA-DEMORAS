from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LAYTIME_", env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://laytime:laytime_dev_pw@localhost:5432/laytime"
    storage_dir: str = "./var/storage"
    cors_origins: list[str] = ["http://localhost:3000"]

    @property
    def normalized_database_url(self) -> str:
        """Hosting providers (Render, Railway, etc.) typically hand out a bare
        postgres://... or postgresql://... URL, which SQLAlchemy defaults to the
        psycopg2 dialect for — but this project depends on psycopg (v3), not
        psycopg2. Force the +psycopg driver regardless of what scheme we're
        given, so LAYTIME_DATABASE_URL never has to be hand-edited per provider.
        """
        url = self.database_url
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://") :]
        if url.startswith("postgresql://"):
            url = "postgresql+psycopg://" + url[len("postgresql://") :]
        return url


settings = Settings()
