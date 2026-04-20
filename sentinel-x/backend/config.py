from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    anthropic_api_key: str = ""
    database_url: str = "sqlite+aiosqlite:///./sentinel_x.db"

    # Scraper settings
    realtime_poll_interval_seconds: int = 60
    historical_window_days: int = 180
    max_concurrent_scrapers: int = 5

    # WebSocket
    ws_heartbeat_interval: int = 30

    # Claude model
    claude_model: str = "claude-sonnet-4-6"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
