from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql://musically_user:password@localhost/musically"
    
    # AWS
    AWS_REGION: str = "us-east-1"
    AWS_SECRET_NAME: str = "musically/jwt-secret"
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    STAGE: str = "dev"  # deployment stage
    
    # AWS S3
    S3_BUCKET_NAME: str = "musically-content-dev"
    S3_CONTENT_PREFIX: str = "content/"
    S3_PRESIGNED_URL_EXPIRE_SECONDS: int = 3600  # 1 hour
    S3_DOWNLOAD_URL_EXPIRE_SECONDS: int = 300    # 5 minutes
    
    # JWT
    SECRET_KEY: str = "your-local-development-secret-key"  # Fallback for local dev
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 240  # 4 hours
    REFRESH_TOKEN_EXPIRE_DAYS: int = 90     # 90 days
    
    # OAuth - Google (Web Client)
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/google/callback"
    
    # OAuth - Google (iOS Client)
    GOOGLE_IOS_CLIENT_ID: str = ""
    
    # Firebase Configuration
    FIREBASE_PROJECT_ID: str = ""
    FIREBASE_PRIVATE_KEY_ID: str = ""
    FIREBASE_PRIVATE_KEY: str = ""
    FIREBASE_CLIENT_EMAIL: str = ""
    FIREBASE_CLIENT_ID: str = ""
    FIREBASE_CLIENT_X509_CERT_URL: str = ""
    FIREBASE_WEB_API_KEY: str = ""
    
    # Firebase Client IDs for different platforms
    FIREBASE_ANDROID_CLIENT_ID: str = ""
    FIREBASE_WEB_CLIENT_ID: str = ""
    FIREBASE_IOS_CLIENT_ID: str = ""
    
    # OAuth - Apple
    APPLE_TEAM_ID: str = ""
    APPLE_CLIENT_ID: str = ""
    APPLE_KEY_ID: str = ""
    APPLE_PRIVATE_KEY_PATH: Optional[str] = None
    APPLE_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/apple/callback"
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # CORS
    FRONTEND_URL: str = "http://localhost:3000"
    BACKEND_CORS_ORIGINS: list = ["http://localhost:3000", "http://localhost:8000"]
    
    # Mobile app configurations
    ALLOW_MOBILE_ORIGINS: bool = True  # Allow requests from mobile apps
    
    # App
    PROJECT_NAME: str = "Musically API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()