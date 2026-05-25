from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    database_url: str
    auth0_domain: str
    auth0_api_audience: str
    auth0_algorithms: str = "RS256"
    cors_origins: str = "http://localhost:5173"
    ingest_api_key: str | None = None
    data_dir: str = "data"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def auth0_algorithms_list(self) -> list[str]:
        return [alg.strip() for alg in self.auth0_algorithms.split(",") if alg.strip()]


settings = Settings()
