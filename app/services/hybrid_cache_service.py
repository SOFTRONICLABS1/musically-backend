import json
import logging
import time
from typing import Any, Optional, Dict, List
from uuid import UUID
from datetime import datetime, timedelta
import threading
import hashlib

# Optional imports with fallbacks
try:
    import boto3
    from botocore.exceptions import ClientError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("boto3 not available, falling back to memory-only cache")

try:
    from app.core.config import settings
except ImportError:
    # Fallback settings for when config is not available
    class FallbackSettings:
        AWS_REGION = "us-east-1"
        STAGE = "dev"
    settings = FallbackSettings()

logger = logging.getLogger(__name__)


class HybridCacheService:
    """
    Multi-tier caching system:
    1. In-memory Lambda cache (fastest, limited lifetime)
    2. DynamoDB cache (persistent, cost-effective)
    3. Redis fallback (if available)
    """
    
    _instance = None
    _lock = threading.Lock()
    _memory_cache = {}
    _cache_stats = {"hits": 0, "misses": 0, "memory_hits": 0, "dynamo_hits": 0, "redis_hits": 0}
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """Initialize DynamoDB client and Redis fallback"""
        try:
            # Check if boto3 is available
            if not BOTO3_AVAILABLE:
                logger.warning("DynamoDB not available, using memory-only cache")
                self.dynamodb = None
                self.cache_table = None
                self.session_table = None
            else:
                self.dynamodb = boto3.resource('dynamodb', region_name=settings.AWS_REGION)
                self.cache_table_name = f"musically-cache-{settings.STAGE}"
                self.session_table_name = f"musically-sessions-{settings.STAGE}"
                
                # Try to get/create cache table
                self._ensure_cache_table()
                self._ensure_session_table()
            
            # Try Redis as fallback
            self.redis_available = False
            try:
                from app.services.redis_service import redis_service
                self.redis_service = redis_service
                self.redis_available = redis_service.is_available()
                if self.redis_available:
                    logger.info("✅ Redis available as fallback cache")
            except ImportError:
                logger.info("📝 Redis service not available, using hybrid cache only")
            
            # Memory cache settings
            self.max_memory_items = 1000  # Limit memory usage
            self.memory_ttl = 300  # 5 minutes max in Lambda memory
            
            logger.info("✅ Hybrid cache service initialized")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize hybrid cache: {e}")
            raise
    
    def _ensure_cache_table(self):
        """Create DynamoDB cache table if it doesn't exist"""
        if not BOTO3_AVAILABLE or not self.dynamodb:
            logger.info("DynamoDB not available, skipping cache table setup")
            return
            
        try:
            table = self.dynamodb.Table(self.cache_table_name)
            table.load()  # Check if table exists
            self.cache_table = table
            logger.info(f"✅ Using existing cache table: {self.cache_table_name}")
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                logger.info(f"📝 Creating cache table: {self.cache_table_name}")
                self._create_cache_table()
            else:
                raise
        except Exception as e:
            logger.warning(f"Could not setup cache table: {e}")
            self.cache_table = None
    
    def _create_cache_table(self):
        """Create DynamoDB cache table with TTL"""
        try:
            table = self.dynamodb.create_table(
                TableName=self.cache_table_name,
                KeySchema=[
                    {'AttributeName': 'cache_key', 'KeyType': 'HASH'}
                ],
                AttributeDefinitions=[
                    {'AttributeName': 'cache_key', 'AttributeType': 'S'}
                ],
                BillingMode='PAY_PER_REQUEST',  # On-demand pricing
                TimeToLiveSpecification={
                    'AttributeName': 'expires_at',
                    'Enabled': True
                }
            )
            
            # Wait for table to be created
            table.wait_until_exists()
            self.cache_table = table
            logger.info(f"✅ Created cache table: {self.cache_table_name}")
            
        except Exception as e:
            logger.error(f"❌ Failed to create cache table: {e}")
            raise
    
    def _ensure_session_table(self):
        """Create DynamoDB session table if it doesn't exist"""
        if not BOTO3_AVAILABLE or not self.dynamodb:
            logger.info("DynamoDB not available, skipping session table setup")
            return
            
        try:
            table = self.dynamodb.Table(self.session_table_name)
            table.load()
            self.session_table = table
            logger.info(f"✅ Using existing session table: {self.session_table_name}")
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                logger.info(f"📝 Creating session table: {self.session_table_name}")
                self._create_session_table()
            else:
                raise
        except Exception as e:
            logger.warning(f"Could not setup session table: {e}")
            self.session_table = None
    
    def _create_session_table(self):
        """Create DynamoDB session table with TTL"""
        try:
            table = self.dynamodb.create_table(
                TableName=self.session_table_name,
                KeySchema=[
                    {'AttributeName': 'session_id', 'KeyType': 'HASH'}
                ],
                AttributeDefinitions=[
                    {'AttributeName': 'session_id', 'AttributeType': 'S'}
                ],
                BillingMode='PAY_PER_REQUEST',
                TimeToLiveSpecification={
                    'AttributeName': 'expires_at',
                    'Enabled': True
                }
            )
            
            table.wait_until_exists()
            self.session_table = table
            logger.info(f"✅ Created session table: {self.session_table_name}")
            
        except Exception as e:
            logger.error(f"❌ Failed to create session table: {e}")
            raise
    
    def _cleanup_memory_cache(self):
        """Remove expired items from memory cache"""
        current_time = time.time()
        expired_keys = []
        
        for key, data in self._memory_cache.items():
            if data['expires_at'] < current_time:
                expired_keys.append(key)
        
        for key in expired_keys:
            del self._memory_cache[key]
        
        # Limit memory cache size
        if len(self._memory_cache) > self.max_memory_items:
            # Remove oldest items
            sorted_items = sorted(
                self._memory_cache.items(),
                key=lambda x: x[1]['created_at']
            )
            items_to_remove = len(self._memory_cache) - self.max_memory_items
            for i in range(items_to_remove):
                key = sorted_items[i][0]
                del self._memory_cache[key]
    
    def set(self, key: str, value: Any, expire_seconds: int = 300) -> bool:
        """Set cache value with multi-tier storage"""
        try:
            serialized_value = json.dumps(value, default=self._json_serializer)
            current_time = time.time()
            expires_at = current_time + expire_seconds
            
            # 1. Store in memory cache (fastest access)
            if expire_seconds <= self.memory_ttl:
                self._cleanup_memory_cache()
                self._memory_cache[key] = {
                    'value': serialized_value,
                    'expires_at': expires_at,
                    'created_at': current_time
                }
            
            # 2. Store in DynamoDB (persistent)
            if self.cache_table:
                try:
                    self.cache_table.put_item(
                        Item={
                            'cache_key': key,
                            'cache_value': serialized_value,
                            'created_at': int(current_time),
                            'expires_at': int(expires_at)
                        }
                    )
                except Exception as e:
                    logger.warning(f"DynamoDB cache set failed for {key}: {e}")
            
            # 3. Store in Redis (if available)
            if self.redis_available:
                try:
                    self.redis_service.set(key, value, expire_seconds)
                except Exception as e:
                    logger.warning(f"Redis cache set failed for {key}: {e}")
            
            return True
            
        except Exception as e:
            logger.error(f"Cache set failed for {key}: {e}")
            return False
    
    def get(self, key: str) -> Optional[Any]:
        """Get cache value from multi-tier storage"""
        try:
            # 1. Check memory cache first (fastest)
            current_time = time.time()
            if key in self._memory_cache:
                data = self._memory_cache[key]
                if data['expires_at'] > current_time:
                    self._cache_stats['hits'] += 1
                    self._cache_stats['memory_hits'] += 1
                    return json.loads(data['value'])
                else:
                    del self._memory_cache[key]
            
            # 2. Check DynamoDB cache
            if self.cache_table:
                try:
                    response = self.cache_table.get_item(
                        Key={'cache_key': key}
                    )
                    
                    if 'Item' in response:
                        item = response['Item']
                        if item['expires_at'] > current_time:
                            value = json.loads(item['cache_value'])
                            
                            # Store back in memory cache for next access
                            if item['expires_at'] - current_time <= self.memory_ttl:
                                self._memory_cache[key] = {
                                    'value': item['cache_value'],
                                    'expires_at': item['expires_at'],
                                    'created_at': current_time
                                }
                            
                            self._cache_stats['hits'] += 1
                            self._cache_stats['dynamo_hits'] += 1
                            return value
                            
                except Exception as e:
                    logger.warning(f"DynamoDB cache get failed for {key}: {e}")
            
            # 3. Check Redis fallback
            if self.redis_available:
                try:
                    redis_value = self.redis_service.get(key)
                    if redis_value is not None:
                        self._cache_stats['hits'] += 1
                        self._cache_stats['redis_hits'] += 1
                        return redis_value
                except Exception as e:
                    logger.warning(f"Redis cache get failed for {key}: {e}")
            
            # Cache miss
            self._cache_stats['misses'] += 1
            return None
            
        except Exception as e:
            logger.error(f"Cache get failed for {key}: {e}")
            self._cache_stats['misses'] += 1
            return None
    
    def delete(self, key: str) -> bool:
        """Delete from all cache tiers"""
        success = True
        
        # Delete from memory
        if key in self._memory_cache:
            del self._memory_cache[key]
        
        # Delete from DynamoDB
        if self.cache_table:
            try:
                self.cache_table.delete_item(Key={'cache_key': key})
            except Exception as e:
                logger.warning(f"DynamoDB cache delete failed for {key}: {e}")
                success = False
        
        # Delete from Redis
        if self.redis_available:
            try:
                self.redis_service.delete(key)
            except Exception as e:
                logger.warning(f"Redis cache delete failed for {key}: {e}")
        
        return success
    
    def delete_pattern(self, pattern: str) -> int:
        """Delete keys matching pattern (limited implementation)"""
        deleted_count = 0
        
        # Clear memory cache matching pattern
        keys_to_delete = []
        for key in self._memory_cache:
            if self._matches_pattern(key, pattern):
                keys_to_delete.append(key)
        
        for key in keys_to_delete:
            del self._memory_cache[key]
            deleted_count += 1
        
        # For DynamoDB, we'd need to scan (expensive), so skip for now
        # In production, consider using GSI with pattern-based keys
        
        # Delete from Redis
        if self.redis_available:
            try:
                redis_deleted = self.redis_service.delete_pattern(pattern)
                deleted_count += redis_deleted
            except Exception as e:
                logger.warning(f"Redis pattern delete failed: {e}")
        
        return deleted_count
    
    def _matches_pattern(self, key: str, pattern: str) -> bool:
        """Simple pattern matching (supports * wildcard)"""
        if pattern == "*":
            return True
        if pattern.endswith("*"):
            return key.startswith(pattern[:-1])
        if pattern.startswith("*"):
            return key.endswith(pattern[1:])
        return key == pattern
    
    def get_stats(self) -> Dict:
        """Get cache performance statistics"""
        total_requests = self._cache_stats['hits'] + self._cache_stats['misses']
        hit_rate = (self._cache_stats['hits'] / total_requests * 100) if total_requests > 0 else 0
        
        return {
            'total_requests': total_requests,
            'hits': self._cache_stats['hits'],
            'misses': self._cache_stats['misses'],
            'hit_rate': round(hit_rate, 2),
            'memory_hits': self._cache_stats['memory_hits'],
            'dynamo_hits': self._cache_stats['dynamo_hits'],
            'redis_hits': self._cache_stats['redis_hits'],
            'memory_cache_size': len(self._memory_cache),
            'redis_available': self.redis_available
        }
    
    # Session management methods
    def set_session(self, session_id: str, session_data: Dict, expire_seconds: int = 3600) -> bool:
        """Store user session in DynamoDB"""
        if not self.session_table:
            logger.warning("Session table not available, cannot store session")
            return False
            
        try:
            expires_at = int(time.time()) + expire_seconds
            
            self.session_table.put_item(
                Item={
                    'session_id': session_id,
                    'session_data': json.dumps(session_data, default=self._json_serializer),
                    'created_at': int(time.time()),
                    'expires_at': expires_at
                }
            )
            return True
            
        except Exception as e:
            logger.error(f"Session set failed for {session_id}: {e}")
            return False
    
    def get_session(self, session_id: str) -> Optional[Dict]:
        """Get user session from DynamoDB"""
        if not self.session_table:
            return None
            
        try:
            response = self.session_table.get_item(
                Key={'session_id': session_id}
            )
            
            if 'Item' in response:
                item = response['Item']
                if item['expires_at'] > time.time():
                    return json.loads(item['session_data'])
            
            return None
            
        except Exception as e:
            logger.error(f"Session get failed for {session_id}: {e}")
            return None
    
    def delete_session(self, session_id: str) -> bool:
        """Delete user session"""
        if not self.session_table:
            return False
            
        try:
            self.session_table.delete_item(Key={'session_id': session_id})
            return True
        except Exception as e:
            logger.error(f"Session delete failed for {session_id}: {e}")
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
    
    def is_available(self) -> bool:
        """Check if caching service is available"""
        return True  # Always available since it uses in-memory as fallback


# Global instance
hybrid_cache = HybridCacheService()