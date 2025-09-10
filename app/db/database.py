from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError, TimeoutError
from app.core.config import settings
import logging
import time
import random

logger = logging.getLogger(__name__)

# Create engine with conservative settings for Aurora Serverless
engine = create_engine(
    settings.DATABASE_URL,
    pool_size=2,  # Balanced pool for performance vs connection limits
    max_overflow=2,  # Allow some overflow for peak traffic
    pool_pre_ping=True,  # Verify connections before using
    pool_recycle=300,  # Recycle connections every 5 minutes
    pool_timeout=20,  # Reduced timeout for faster failover
    connect_args={
        "connect_timeout": 8,  # Faster connection establishment
        "options": "-c statement_timeout=25000",  # 25 second statement timeout
        "sslmode": "require"  # Ensure SSL is used
    }
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Global state for wake-up tracking
_last_wake_attempt = 0
_wake_cooldown = 30  # seconds


def wake_cold_database():
    """Internal function to wake up cold Aurora Serverless database with cooldown"""
    global _last_wake_attempt
    
    current_time = time.time()
    
    # Check if we recently attempted a wake-up (circuit breaker pattern)
    if current_time - _last_wake_attempt < _wake_cooldown:
        logger.info(f"⏸️ Wake-up attempted recently, skipping (cooldown: {_wake_cooldown}s)")
        return False
    
    _last_wake_attempt = current_time
    logger.info("🔥 Detected cold database, warming up Aurora Serverless...")
    
    try:
        # Simple wake-up query with longer timeout
        db = SessionLocal()
        start_time = time.time()
        
        # Test connection with a simple query
        db.execute(text("SELECT 1 as wake_test"))
        
        end_time = time.time()
        wake_time = round(end_time - start_time, 2)
        
        logger.info(f"✅ Database warmed up successfully in {wake_time}s")
        db.close()
        return True
        
    except Exception as e:
        logger.warning(f"⏳ Database still scaling during warm-up: {str(e)[:100]}...")
        if 'db' in locals():
            db.close()
        return False


def get_db_with_retry(max_retries=3, base_delay=1.0):
    """Get database session with retry logic and auto-wake for Aurora Serverless scaling"""
    last_error = None
    database_warmed = False
    
    for attempt in range(max_retries):
        db = None
        try:
            db = SessionLocal()
            # Test connection immediately
            db.execute(text("SELECT 1"))
            yield db
            return
            
        except (OperationalError, TimeoutError) as e:
            last_error = e
            if db is not None:
                db.close()
            
            # Check if this looks like a cold database issue
            error_msg = str(e).lower()
            is_cold_database = any(indicator in error_msg for indicator in [
                'timeout', 'connection timed out', 'queuepool limit', 'connection refused'
            ])
            
            if is_cold_database and not database_warmed and attempt == 0:
                logger.info("🔍 Cold database detected, attempting internal warm-up...")
                if wake_cold_database():
                    database_warmed = True
                    # Try again immediately after successful warm-up
                    continue
            
            if attempt < max_retries - 1:
                # Exponential backoff with jitter
                delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                logger.warning(f"Database connection attempt {attempt + 1} failed, retrying in {delay:.2f}s: {str(e)[:100]}...")
                time.sleep(delay)
            else:
                logger.error(f"Database connection failed after {max_retries} attempts: {str(e)}")
                raise last_error
                
        except Exception as e:
            if db is not None:
                db.close()
            logger.error(f"Unexpected database error: {str(e)}")
            raise e
        finally:
            # Ensure session is always closed when exiting
            if db is not None:
                try:
                    db.close()
                except:
                    pass


def get_db():
    """Standard dependency to get DB session with retry logic"""
    try:
        yield from get_db_with_retry()
    except Exception as e:
        logger.error(f"Database session failed: {str(e)}")
        raise e


def execute_with_retry(query_func, max_retries=3):
    """Execute database query with retry logic and auto-wake for cold database"""
    last_error = None
    database_warmed = False
    
    for attempt in range(max_retries):
        try:
            db = SessionLocal()
            result = query_func(db)
            return result
            
        except (OperationalError, TimeoutError) as e:
            last_error = e
            
            # Check if this looks like a cold database issue
            error_msg = str(e).lower()
            is_cold_database = any(indicator in error_msg for indicator in [
                'timeout', 'connection timed out', 'queuepool limit', 'connection refused'
            ])
            
            if is_cold_database and not database_warmed and attempt == 0:
                logger.info("🔍 Cold database detected in query execution, attempting internal warm-up...")
                if wake_cold_database():
                    database_warmed = True
                    # Try again immediately after successful warm-up
                    continue
            
            if attempt < max_retries - 1:
                delay = 1.0 + (attempt * 0.5) + random.uniform(0, 0.5)
                logger.warning(f"Query attempt {attempt + 1} failed, retrying in {delay:.2f}s: {str(e)[:100]}...")
                time.sleep(delay)
                
        except Exception as e:
            logger.error(f"Query failed with unexpected error: {str(e)}")
            raise e
        finally:
            if 'db' in locals():
                db.close()
    
    logger.error(f"Query failed after {max_retries} attempts: {str(last_error)}")
    raise last_error