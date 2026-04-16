from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    database_url: str = "sqlite:///./plotr.db"
    secret_key: str = "change-me-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7

    upload_dir: str = "./uploads"
    max_photo_size_mb: int = 20
    max_video_size_mb: int = 200

    class Config:
        env_file = ".env"


settings = Settings()
