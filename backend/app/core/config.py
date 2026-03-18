from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    DATABASE_URL: str
    REDIS_URL: str
    APP_ENV: str = "development"
    SECRET_KEY: str
    DEBUG: bool = True
    UPLOAD_DIR: str
    MAX_USER_STORAGE_GB: int = 1
    ANTHROPIC_API_KEY: Optional[str] = None

    class Config:
        env_file = ".env"

settings = Settings()
