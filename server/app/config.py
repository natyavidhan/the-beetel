"""
Application configuration — reads from environment variables / .env file.
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Central configuration pulled from environment variables."""

    # MongoDB
    MONGO_URI: str = os.getenv("MONGO_URI", "mongodb://localhost:27017/beetel")
    DB_NAME: str = "beetel"

    # Session / security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "change-me")

    # Admin login
    ADMIN_USER: str = os.getenv("ADMIN_USER", "admin")
    ADMIN_PASS: str = os.getenv("ADMIN_PASS", "changeme")

    # ESP32 API key
    ESP32_API_KEY: str = os.getenv("ESP32_API_KEY", "")

    # Spotify (optional — for metadata lookup & playback proxy)
    SPOTIFY_CLIENT_ID: str = os.getenv("SPOTIFY_CLIENT_ID", "")
    SPOTIFY_CLIENT_SECRET: str = os.getenv("SPOTIFY_CLIENT_SECRET", "")
    SPOTIFY_REFRESH_TOKEN: str = os.getenv("SPOTIFY_REFRESH_TOKEN", "")


settings = Settings()
