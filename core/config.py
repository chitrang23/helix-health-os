import os
from typing import List

class Settings:
    PROJECT_NAME: str = "Helix Health OS"
    SECRET_KEY: str = os.getenv("SECRET_KEY", "prod-health-super-secret-key-change-in-env-99021")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 60 * 24))
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./helix.db")
    
    # Strict CORS Origins Whitelist (Never use wildcard '*' when credentials are true)
    ALLOWED_CORS_ORIGINS: List[str] = [
        origin.strip() for origin in os.getenv(
            "HELIX_CORS_ORIGINS",
            "http://localhost:3000,http://localhost:8000,http://127.0.0.1:8000,http://127.0.0.1:3000,http://localhost:5173"
        ).split(",") if origin.strip()
    ]
    
    # Safe Upload Constraints
    MAX_UPLOAD_SIZE_MB: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", 25))
    
    # Gemini API Key configuration
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

settings = Settings()