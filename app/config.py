from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application and database configuration loaded from environment variables."""

    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000

    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_USER: str = "postgres"
    DB_PASSWORD: str = "postgres"
    DB_NAME: str = "orders_db"

    DB_CONNECT_RETRIES: int = 5
    DB_CONNECT_RETRY_DELAY: float = 1.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def conninfo(self) -> str:
        """PostgreSQL connection string."""
        return (
            f"host={self.DB_HOST} "
            f"port={self.DB_PORT} "
            f"user={self.DB_USER} "
            f"password={self.DB_PASSWORD} "
            f"dbname={self.DB_NAME}"
        )


settings = Settings()
