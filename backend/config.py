from pydantic import BaseSettings


class AppSettings(BaseSettings):
    app_name: str = "Israel Market Importer PRO"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000
    playwright_headless: bool = True
    request_timeout: int = 30
    user_agent: str = "Mozilla/5.0 (compatible; IsraelMarketImporterPRO/1.0)"

    class Config:
        env_file = ".env"
