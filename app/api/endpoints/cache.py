from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from app.services.hybrid_cache_service import hybrid_cache
from app.core.dependencies import get_current_user
from app.models.user import User
import logging

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Cache"])


@router.get("/stats")
async def get_cache_stats(current_user: User = Depends(get_current_user)):
    """
    Get Redis cache statistics - for debugging/monitoring
    Only accessible to authenticated users
    """
    try:
        # Get hybrid cache statistics
        stats = hybrid_cache.get_stats()
        
        # Add additional details
        enhanced_stats = {
            "status": "available" if hybrid_cache.is_available() else "unavailable",
            "cache_type": "hybrid",
            "layers": {
                "memory": "in-lambda",
                "persistent": "dynamodb",
                "fallback": "redis" if stats.get("redis_available") else "none"
            },
            **stats
        }
        
        return enhanced_stats
        
    except Exception as e:
        logger.error(f"Cache stats error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get cache statistics"
        )


@router.post("/clear")
async def clear_cache(
    pattern: str = "*",
    current_user: User = Depends(get_current_user)
):
    """
    Clear cache by pattern - for debugging/admin use
    Only accessible to authenticated users
    """
    try:
        # Safety check - don't allow clearing everything in production
        if pattern == "*":
            pattern = "content:*"  # Default to content cache only
        
        deleted_count = hybrid_cache.delete_pattern(pattern)
        
        return {
            "status": "success",
            "pattern": pattern,
            "deleted_keys": deleted_count,
            "cache_type": "hybrid"
        }
        
    except Exception as e:
        logger.error(f"Cache clear error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to clear cache"
        )


@router.get("/health")
async def cache_health():
    """
    Cache health check endpoint - no authentication required
    """
    try:
        # Test hybrid cache operations
        test_key = "health_check_test"
        hybrid_cache.set(test_key, "test_value", 10)
        value = hybrid_cache.get(test_key)
        hybrid_cache.delete(test_key)
        
        if value == "test_value":
            stats = hybrid_cache.get_stats()
            return {
                "status": "healthy", 
                "cache": "operational",
                "redis_fallback": stats.get("redis_available", False)
            }
        else:
            return {"status": "degraded", "cache": "read_write_issues"}
            
    except Exception as e:
        logger.warning(f"Hybrid cache health check failed: {e}")
        return {"status": "unhealthy", "cache": "connection_error"}