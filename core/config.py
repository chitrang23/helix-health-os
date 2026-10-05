import os

class Settings:
    PROJECT_NAME: str = "Helix Health OS"
    SECRET_KEY: str = os.getenv("SECRET_KEY", "prod-health-super-secret-key-change-in-env-99021")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./helix_production.db")
    ALLOWED_CORS_ORIGINS: list = [
        origin.strip() for origin in os.getenv("HELIX_CORS_ORIGINS", "http://localhost:3000,http://localhost:8000,http://127.0.0.1:8000").split(",") if origin.strip()
    ]

settings = Settings()

MAX_UPLOAD_SIZE_MB = 100

# Added Gemini API Key support
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
