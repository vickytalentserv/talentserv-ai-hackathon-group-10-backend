from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_ignore_empty=True,
    )

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
    openai_enabled: bool = True
    openai_match_rerank: bool = True
    openai_match_rerank_limit: int = 20
    openai_timeout_seconds: float = 20.0
    scrape_enabled: bool = True
    scrape_delay_seconds: float = 2.0
    scrape_playwright_enabled: bool = True
    scrape_playwright_headless: bool = True
    scrape_playwright_channel: str | None = None
    scrape_playwright_timeout_ms: int = 45_000

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def auth0_algorithms_list(self) -> list[str]:
        return [alg.strip() for alg in self.auth0_algorithms.split(",") if alg.strip()]


settings = Settings()
