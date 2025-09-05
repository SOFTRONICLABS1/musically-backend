import sys
import os
import logging
import time

# Add the current directory to Python path for Lambda
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import settings with error handling
try:
    from app.core.config import settings
except ImportError:
    logger.warning("Could not import settings, using defaults")
    class Settings:
        PROJECT_NAME = "Musically"
        VERSION = "1.0.0"
        API_V1_STR = "/api/v1"
        BACKEND_CORS_ORIGINS = ["*"]
    settings = Settings()

# Create FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url="/openapi.json",  # Serve at root level
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS
def get_cors_origins():
    """Get CORS origins based on configuration"""
    origins = getattr(settings, 'BACKEND_CORS_ORIGINS', ["http://localhost:3000", "http://localhost:8000"])
    
    # For mobile apps, we need to allow different origins
    if getattr(settings, 'ALLOW_MOBILE_ORIGINS', True):
        # Mobile apps typically use file:// or capacitor:// protocols
        mobile_origins = [
            "file://",
            "capacitor://localhost",
            "ionic://localhost",
            "http://localhost",
            "https://localhost"
        ]
        # In production, you should specify exact mobile app bundle IDs or schemes
        origins.extend(mobile_origins)
    
    return origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Include API router (with error handling)
try:
    from app.api import api_router
    app.include_router(api_router, prefix=settings.API_V1_STR)
    logger.info("API router loaded successfully")
except Exception as e:
    logger.error(f"Failed to load API router: {e}")
    # Continue without API endpoints for basic health checks

# Root endpoint
@app.get("/")
async def root():
    return {
        "message": "Welcome to Musically API",
        "version": settings.VERSION,
        "docs": "/docs",
        "health": "/health"
    }

# Health check endpoint
@app.get("/health")
async def health_check():
    try:
        from app.services.hybrid_cache_service import hybrid_cache
        cache_stats = hybrid_cache.get_stats()
        cache_info = {
            "available": hybrid_cache.is_available(),
            "hit_rate": cache_stats.get("hit_rate", 0),
            "redis_fallback": cache_stats.get("redis_available", False)
        }
    except Exception as e:
        logger.warning(f"Cache service not available: {e}")
        cache_info = {"available": False, "error": str(e)}
    
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": "lambda",
        "cache": cache_info
    }


# Startup event
@app.on_event("startup")
async def startup_event():
    try:
        logger.info(f"Starting {settings.PROJECT_NAME} v{settings.VERSION}")
        logger.info(f"Python path: {sys.path[:3]}")
        
        # Warm up database connection
        await warm_database_connection()
        
        # Initialize Firebase service
        await warm_firebase_service()
        
        # Warm up hybrid cache
        await warm_hybrid_cache()
        
    except Exception as e:
        logger.error(f"Startup error: {e}")


async def warm_database_connection():
    """Warm up database connection during Lambda startup"""
    try:
        from app.db.database import SessionLocal
        from sqlalchemy import text
        
        logger.info("🔥 Warming up database connection...")
        start_time = time.time()
        
        db = SessionLocal()
        # Simple connection test
        db.execute(text("SELECT 1 as warmup"))
        db.close()
        
        end_time = time.time()
        logger.info(f"✅ Database warmed up in {round(end_time - start_time, 2)}s")
        
    except Exception as e:
        logger.warning(f"⚠️ Database warmup failed (will retry during requests): {e}")


async def warm_firebase_service():
    """Initialize Firebase service during startup"""
    try:
        from app.services.firebase_service import FirebaseService
        
        logger.info("🔥 Initializing Firebase service...")
        FirebaseService.initialize()
        logger.info("✅ Firebase service initialized")
        
    except Exception as e:
        logger.warning(f"⚠️ Firebase initialization failed (will retry during requests): {e}")


async def warm_hybrid_cache():
    """Warm up hybrid cache with frequently accessed data"""
    try:
        logger.info("🔥 Warming up hybrid cache...")
        start_time = time.time()
        
        # Import with error handling
        from app.services.hybrid_cache_service import hybrid_cache
        from app.db.database import SessionLocal
        
        # Test basic cache operations
        hybrid_cache.set("warmup_test", "test_value", 60)
        test_value = hybrid_cache.get("warmup_test")
        if test_value == "test_value":
            logger.info("✅ Cache basic operations working")
        
        # Try to warm up content if possible
        try:
            from app.services.content_service import ContentService
            from app.schemas.content import ContentFilters
            
            db = SessionLocal()
            try:
                # Warm up public content cache (first page)
                filters = ContentFilters(page=1, per_page=20)
                ContentService.get_public_content(db, filters)
                logger.info("✅ Warmed public content cache")
            finally:
                db.close()
        except Exception as e:
            logger.info(f"Content warming skipped: {e}")
        
        # Clear any old cache patterns that might be stale
        try:
            hybrid_cache.delete_pattern("content:list:*")
            hybrid_cache.delete_pattern("user:*")
            logger.info("✅ Cleared stale cache patterns")
        except Exception as e:
            logger.info(f"Cache cleanup skipped: {e}")
        
        end_time = time.time()
        logger.info(f"✅ Hybrid cache warmed up in {round(end_time - start_time, 2)}s")
        
    except Exception as e:
        logger.warning(f"⚠️ Hybrid cache warming failed: {e}")

# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    logger.info(f"Shutting down {settings.PROJECT_NAME}")

# Lambda handler for API Gateway
handler = Mangum(app, lifespan="off")

# For local development
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )