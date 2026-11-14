import os
from typing import List
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # App Settings
    APP_NAME: str = "PolicyPath AI API"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    DEBUG: bool = ENVIRONMENT.lower() == "development"

    # CORS Whitelist
    ALLOWED_ORIGINS: List[str] = [
        "https://policy-path-theta.vercel.app",
        "https://policypath.in",
        "https://www.policypath.in",
        "http://localhost:5173",
        "http://localhost:3000",
    ]

    # Groq API
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")

    # Supabase Setup
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_ANON_KEY: str = os.getenv("SUPABASE_ANON_KEY", "")
    SUPABASE_SERVICE_ROLE_KEY: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

    # Security & Limits
    DEFAULT_RATE_LIMIT: str = "20/minute"
    MAX_QUERY_LENGTH: int = 2000  # Prevent token depletion attacks

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()

# Validation warning on startup
if not settings.GROQ_API_KEY:
    print("⚠️ WARNING: GROQ_API_KEY is not set. AI features will fail!")
if not settings.SUPABASE_URL or not settings.SUPABASE_ANON_KEY:
    print("⚠️ WARNING: Supabase credentials are missing. Auth validation will run in guest fallback mode.")
