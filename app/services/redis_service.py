import redis
import json
import logging
from typing import Any, Optional, Dict, List
from uuid import UUID
from datetime import datetime, timedelta
from app.core.config import settings

logger = logging.getLogger(__name__)


class RedisService:
    """
    Redis service for caching with connection pooling and error handling
    """
    
    _instance = None
    _redis_client = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize_redis()
        return cls._instance
    
    def _initialize_redis(self):
        """Initialize Redis connection with error handling"""
        try:
            self._redis_client = redis.from_url(
                settings.REDIS_URL,
                encoding='utf-8',
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30,
                max_connections=20
            )
            # Test connection
            self._redis_client.ping()
            logger.info("✅ Redis connection established successfully")
            
        except Exception as e:
            logger.warning(f"⚠️ Redis connection failed: {e}")
            self._redis_client = None
    
    @property
    def client(self):
        """Get Redis client with health check"""
        if self._redis_client is None:
            return None
            
        try:
            self._redis_client.ping()
            return self._redis_client
        except Exception as e:
            logger.warning(f"Redis health check failed: {e}")
            self._initialize_redis()
            return self._redis_client
    
    def is_available(self) -> bool:
        """Check if Redis is available"""
        return self.client is not None
    
    def set(self, key: str, value: Any, expire_seconds: int = 300) -> bool:
        """Set a key-value pair with expiration"""
        if not self.is_available():
            return False
            
        try:
            serialized_value = json.dumps(value, default=self._json_serializer)
            self.client.setex(key, expire_seconds, serialized_value)
            return True
        except Exception as e:
            logger.error(f"Redis SET error for key {key}: {e}")
            return False
    
    def get(self, key: str) -> Optional[Any]:
        """Get value by key"""
        if not self.is_available():
            return None
            
        try:
            value = self.client.get(key)
            if value is None:
                return None
            return json.loads(value)
        except Exception as e:
            logger.error(f"Redis GET error for key {key}: {e}")
            return None
    
    def delete(self, key: str) -> bool:
        """Delete a key"""
        if not self.is_available():
            return False
            
        try:
            return bool(self.client.delete(key))
        except Exception as e:
            logger.error(f"Redis DELETE error for key {key}: {e}")
            return False
    
    def delete_pattern(self, pattern: str) -> int:
        """Delete keys matching a pattern"""
        if not self.is_available():
            return 0
            
        try:
            keys = self.client.keys(pattern)
            if keys:
                return self.client.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"Redis DELETE_PATTERN error for pattern {pattern}: {e}")
            return 0
    
    def exists(self, key: str) -> bool:
        """Check if key exists"""
        if not self.is_available():
            return False
            
        try:
            return bool(self.client.exists(key))
        except Exception as e:
            logger.error(f"Redis EXISTS error for key {key}: {e}")
            return False
    
    def increment(self, key: str, amount: int = 1, expire_seconds: Optional[int] = None) -> Optional[int]:
        """Increment a key's value"""
        if not self.is_available():
            return None
            
        try:
            value = self.client.incr(key, amount)
            if expire_seconds:
                self.client.expire(key, expire_seconds)
            return value
        except Exception as e:
            logger.error(f"Redis INCR error for key {key}: {e}")
            return None
    
    def get_multiple(self, keys: List[str]) -> Dict[str, Any]:
        """Get multiple keys at once"""
        if not self.is_available() or not keys:
            return {}
            
        try:
            values = self.client.mget(keys)
            result = {}
            for key, value in zip(keys, values):
                if value is not None:
                    try:
                        result[key] = json.loads(value)
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to deserialize value for key {key}")
            return result
        except Exception as e:
            logger.error(f"Redis MGET error: {e}")
            return {}
    
    def set_multiple(self, data: Dict[str, Any], expire_seconds: int = 300) -> bool:
        """Set multiple key-value pairs"""
        if not self.is_available() or not data:
            return False
            
        try:
            pipe = self.client.pipeline()
            for key, value in data.items():
                serialized_value = json.dumps(value, default=self._json_serializer)
                pipe.setex(key, expire_seconds, serialized_value)
            pipe.execute()
            return True
        except Exception as e:
            logger.error(f"Redis MSET error: {e}")
            return False
    
    @staticmethod
    def _json_serializer(obj):
        """Custom JSON serializer for complex objects"""
        if isinstance(obj, UUID):
            return str(obj)
        elif isinstance(obj, datetime):
            return obj.isoformat()
        elif hasattr(obj, '__dict__'):
            return obj.__dict__
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


# Cache key generators
class CacheKeys:
    """Central place for cache key patterns"""
    
    # Content caching
    CONTENT_BY_ID = "content:id:{content_id}:{user_id}"
    CONTENT_LIST_USER = "content:list:user:{user_id}:{page}:{filters_hash}"
    CONTENT_LIST_PUBLIC = "content:list:public:{page}:{filters_hash}"
    CONTENT_DOWNLOAD_URL = "content:download:{content_id}:{attachment}"
    
    # User caching
    USER_BY_ID = "user:id:{user_id}"
    USER_BY_EMAIL = "user:email:{email}"
    
    # Game caching
    GAME_BY_ID = "game:id:{game_id}"
    GAME_CONTENT = "game:content:{game_id}:{page}"
    CONTENT_GAMES = "content:games:{content_id}:{page}"
    
    # Auth caching
    FIREBASE_TOKEN = "auth:firebase:{token_hash}"
    USER_PERMISSIONS = "auth:permissions:{user_id}"
    
    # Search caching
    SEARCH_RESULTS = "search:{query_hash}:{page}:{filters_hash}"
    
    @staticmethod
    def format_key(pattern: str, **kwargs) -> str:
        """Format cache key with parameters"""
        return pattern.format(**kwargs)
    
    @staticmethod
    def hash_filters(filters: dict) -> str:
        """Create hash for filter parameters"""
        import hashlib
        filter_str = json.dumps(filters, sort_keys=True, default=str)
        return hashlib.md5(filter_str.encode()).hexdigest()[:8]


# Cache decorators
def cache_result(key_pattern: str, expire_seconds: int = 300, use_user_id: bool = True):
    """Decorator to cache function results"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            redis_service = RedisService()
            
            if not redis_service.is_available():
                return func(*args, **kwargs)
            
            # Build cache key
            key_kwargs = kwargs.copy()
            if use_user_id and 'user_id' in kwargs:
                key_kwargs['user_id'] = str(kwargs['user_id'])
            
            cache_key = CacheKeys.format_key(key_pattern, **key_kwargs)
            
            # Try to get from cache
            cached_result = redis_service.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache HIT for key: {cache_key}")
                return cached_result
            
            # Execute function and cache result
            logger.debug(f"Cache MISS for key: {cache_key}")
            result = func(*args, **kwargs)
            
            if result is not None:
                redis_service.set(cache_key, result, expire_seconds)
            
            return result
        return wrapper
    return decorator


def invalidate_cache_pattern(pattern: str):
    """Decorator to invalidate cache patterns after function execution"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            
            redis_service = RedisService()
            if redis_service.is_available():
                deleted_count = redis_service.delete_pattern(pattern)
                if deleted_count > 0:
                    logger.debug(f"Invalidated {deleted_count} cache keys matching pattern: {pattern}")
            
            return result
        return wrapper
    return decorator


# Global instance
redis_service = RedisService()