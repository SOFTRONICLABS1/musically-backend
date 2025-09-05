"""Database status and management endpoints"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session
from app.db.database import get_db, engine, Base
from app.models.user import User, AuthUser, PasswordResetToken, Content, Follow, ContentLike
from app.schemas.database import SchemaValidationResponse, DatabaseHealthResponse
from app.services.schema_validator import SchemaValidator
from app.core.config import settings
import logging
import socket
import os
from urllib.parse import urlparse

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Database"])


@router.get("/status")
async def database_status(db: Session = Depends(get_db)):
    """Check database connection and return status information"""
    try:
        from app.db.database import execute_with_retry
        from sqlalchemy.exc import OperationalError, TimeoutError
        
        def get_db_status(db_session):
            # Test connection
            db_session.execute(text("SELECT 1"))
            
            # Get basic info with faster queries
            result = db_session.execute(text("SELECT current_database(), current_user, version()"))
            row = result.fetchone()
            
            return {
                "database": row[0],
                "user": row[1], 
                "postgresql_version": row[2].split(',')[0]
            }
        
        db_info = execute_with_retry(get_db_status)
        
        return {
            "status": "connected",
            **db_info,
            "message": "Database connection successful"
        }
        
    except (OperationalError, TimeoutError) as e:
        logger.error(f"Database timeout/connection error: {str(e)}")
        return {
            "status": "timeout",
            "message": "Database is scaling or temporarily unavailable. This is normal for Aurora Serverless.",
            "recommendation": "Retry in 10-30 seconds",
            "error": str(e)
        }
    except Exception as e:
        logger.error(f"Database connection error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database connection failed: {str(e)}")


@router.get("/tables")  
async def list_tables():
    """List all tables in the database with row counts (optimized for Aurora Serverless)"""
    import asyncio
    import threading
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
    
    def quick_db_check():
        """Quick database availability check"""
        try:
            from app.db.database import SessionLocal
            from sqlalchemy import text
            
            db = SessionLocal()
            db.execute(text("SELECT 1"))
            db.close()
            return True
        except:
            return False
    
    # First, do a very quick availability check with 5-second timeout
    try:
        with ThreadPoolExecutor() as executor:
            future = executor.submit(quick_db_check)
            is_available = future.result(timeout=5)  # 5-second timeout
            
        if not is_available:
            return {
                "status": "database_scaling",
                "message": "🔄 Aurora Serverless is currently scaling up (cold start detected)",
                "recommendation": "Database is warming up. Try again in 30-60 seconds or call POST /api/v1/database/wake-db",
                "expected_tables": ['users', 'auth_users', 'password_reset_tokens', 'content', 'follows', 'content_likes', 'alembic_version'],
                "total_tables": "unknown - database scaling",
                "note": "This is normal behavior for Aurora Serverless during periods of inactivity"
            }
            
    except (FutureTimeoutError, Exception) as e:
        logger.warning(f"Quick database check failed: {str(e)[:100]}")
        return {
            "status": "database_cold_start", 
            "message": "🥶 Aurora Serverless is in cold start state",
            "recommendation": "Database is scaling from 0 capacity. Please wait 60-90 seconds and try again.",
            "expected_tables": ['users', 'auth_users', 'password_reset_tokens', 'content', 'follows', 'content_likes', 'alembic_version'],
            "total_tables": "unknown - cold start",
            "wake_endpoint": "POST /api/v1/database/wake-db",
            "estimated_wait_time": "60-90 seconds"
        }
    
    # If quick check passed, proceed with full query
    try:
        from app.db.database import execute_with_retry
        from sqlalchemy.exc import OperationalError, TimeoutError
        
        def get_table_info(db_session):
            inspector = inspect(engine)
            tables = inspector.get_table_names()
            
            table_info = []
            # Process tables in smaller batches to avoid timeouts
            for table in tables[:5]:  # Limit to first 5 tables for speed
                try:
                    # Use approximate row count for faster queries
                    result = db_session.execute(text(f"SELECT reltuples::bigint FROM pg_class WHERE relname = '{table}'"))
                    count_result = result.fetchone()
                    count = int(count_result[0]) if count_result and count_result[0] is not None else 0
                    
                    # If approximate count is 0, get exact count (but with timeout protection)
                    if count == 0:
                        result = db_session.execute(text(f"SELECT COUNT(*) FROM {table} LIMIT 1000"))
                        count = result.fetchone()[0]
                    
                    # Get columns (cached by inspector)
                    columns = inspector.get_columns(table)
                    
                    table_info.append({
                        "name": table,
                        "row_count": count,
                        "column_count": len(columns),
                        "columns": [col['name'] for col in columns][:5]  # First 5 columns only
                    })
                except Exception as e:
                    logger.warning(f"Error getting info for table {table}: {str(e)}")
                    table_info.append({
                        "name": table,
                        "row_count": -1,  # Indicates error
                        "column_count": 0,
                        "columns": []
                    })
            
            return table_info, tables
        
        table_info, all_tables = execute_with_retry(get_table_info, max_retries=2)
        
        # Check for expected tables
        expected_tables = ['users', 'auth_users', 'password_reset_tokens', 'content', 'follows', 'content_likes', 'alembic_version']
        existing_tables = set(all_tables)
        missing_tables = [t for t in expected_tables if t not in existing_tables]
        
        return {
            "total_tables": len(all_tables),
            "tables": table_info,
            "expected_tables": expected_tables,
            "missing_tables": missing_tables,
            "message": f"Tables retrieved successfully (showing first {len(table_info)} of {len(all_tables)})",
            "note": "Row counts are approximate for performance"
        }
        
    except (OperationalError, TimeoutError) as e:
        logger.warning(f"Database timeout: {str(e)}")
        return {
            "status": "database_scaling",
            "message": "🔄 Aurora Serverless is scaling up. This is normal for cold starts.",
            "recommendation": "Wait 30-60 seconds and try again, or call POST /api/v1/database/wake-db first",
            "expected_tables": ['users', 'auth_users', 'password_reset_tokens', 'content', 'follows', 'content_likes', 'alembic_version'],
            "total_tables": "unknown",
            "error": str(e)[:200]
        }
        
    except Exception as e:
        logger.error(f"Error listing tables: {str(e)}")
        return {
            "status": "error",
            "message": "Database error occurred",
            "error": str(e)[:200],
            "recommendation": "Check database connectivity"
        }


@router.post("/create-tables")
async def create_tables(db: Session = Depends(get_db)):
    """Create all tables defined in models (use with caution in production)"""
    try:
        # Check if tables already exist
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()
        
        if existing_tables and len(existing_tables) > 0:
            return {
                "status": "skipped",
                "message": f"Tables already exist ({len(existing_tables)} tables found). Use Alembic migrations to update schema.",
                "existing_tables": existing_tables
            }
        
        # Create all tables
        Base.metadata.create_all(bind=engine)
        
        # Get list of created tables
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        return {
            "status": "success",
            "message": "Tables created successfully",
            "created_tables": tables
        }
    except Exception as e:
        logger.error(f"Error creating tables: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create tables: {str(e)}")


@router.get("/test-query")
async def test_query(db: Session = Depends(get_db)):
    """Test a simple query to verify database operations"""
    try:
        # Count users
        user_count = db.query(User).count()
        auth_user_count = db.query(AuthUser).count()
        content_count = db.query(Content).count()
        
        # Get sample user if exists
        sample_user = db.query(User).first()
        sample_data = None
        if sample_user:
            sample_data = {
                "id": str(sample_user.id),
                "email": sample_user.email,
                "username": sample_user.username,
                "created_at": sample_user.created_at.isoformat() if sample_user.created_at else None
            }
        
        return {
            "status": "success",
            "counts": {
                "users": user_count,
                "auth_users": auth_user_count,
                "content": content_count
            },
            "sample_user": sample_data,
            "message": "Query executed successfully"
        }
    except Exception as e:
        logger.error(f"Error executing test query: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")


@router.get("/debug-connection")
async def debug_connection():
    """Debug database connection issues"""
    debug_info = {}
    
    try:
        # Parse DATABASE_URL
        parsed = urlparse(settings.DATABASE_URL.replace("postgresql://", "http://"))
        db_host = parsed.hostname
        db_port = parsed.port or 5432
        
        debug_info["database_host"] = db_host
        debug_info["database_port"] = db_port
        
        # Try DNS resolution
        try:
            ip = socket.gethostbyname(db_host)
            debug_info["dns_resolution"] = f"Success - {ip}"
        except Exception as e:
            debug_info["dns_resolution"] = f"Failed - {str(e)}"
            
        # Check environment
        debug_info["environment"] = {
            "AWS_REGION": os.environ.get("AWS_REGION", "not set"),
            "AWS_EXECUTION_ENV": os.environ.get("AWS_EXECUTION_ENV", "not set"),
            "AWS_LAMBDA_FUNCTION_NAME": os.environ.get("AWS_LAMBDA_FUNCTION_NAME", "not set"),
        }
        
        # Try socket connection
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((db_host, db_port))
            sock.close()
            
            if result == 0:
                debug_info["socket_connection"] = "Success - Port is open"
            else:
                debug_info["socket_connection"] = f"Failed - Error code: {result}"
        except Exception as e:
            debug_info["socket_connection"] = f"Failed - {str(e)}"
            
        # Try actual database connection
        try:
            from sqlalchemy import create_engine
            test_engine = create_engine(
                settings.DATABASE_URL,
                connect_args={"connect_timeout": 5}
            )
            with test_engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                debug_info["database_connection"] = "Success"
        except Exception as e:
            debug_info["database_connection"] = f"Failed - {str(e)}"
            
    except Exception as e:
        debug_info["error"] = str(e)
        
    return debug_info


@router.get("/alembic-version")
async def get_alembic_version(db: Session = Depends(get_db)):
    """Get current Alembic migration version"""
    try:
        result = db.execute(text("SELECT version_num FROM alembic_version"))
        version = result.fetchone()
        
        if version:
            return {
                "status": "success",
                "version": version[0],
                "message": "Alembic version retrieved"
            }
        else:
            return {
                "status": "not_found",
                "version": None,
                "message": "No Alembic version found. Migrations may not have been run."
            }
    except Exception as e:
        # Table might not exist
        if "alembic_version" in str(e).lower() or "does not exist" in str(e).lower():
            return {
                "status": "not_initialized",
                "version": None,
                "message": "Alembic not initialized. Run 'alembic upgrade head' to initialize."
            }
        logger.error(f"Error getting Alembic version: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get Alembic version: {str(e)}")


@router.get("/validate-schema", response_model=SchemaValidationResponse)
async def validate_database_schema(db: Session = Depends(get_db)):
    """
    Validate database schema against application models.
    Checks if all expected tables and columns exist and match the SQLAlchemy models.
    """
    try:
        validation_result = SchemaValidator.validate_schema(db)
        return SchemaValidationResponse(**validation_result)
    except Exception as e:
        logger.error(f"Schema validation error: {str(e)}")
        return SchemaValidationResponse(
            is_valid=False,
            error=str(e),
            recommendations=["Failed to validate schema. Check database connection and permissions."]
        )


@router.get("/health")
async def database_health():
    """
    Quick health check for database connectivity and basic schema.
    Optimized for Aurora Serverless with immediate response.
    """
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
    
    def simple_db_test():
        """Simple database test with minimal timeout"""
        try:
            from app.db.database import SessionLocal
            from sqlalchemy import text
            
            db = SessionLocal()
            db.execute(text("SELECT 1"))
            
            # Quick table count
            result = db.execute(text("""
                SELECT COUNT(*) FROM information_schema.tables 
                WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
                LIMIT 1
            """))
            tables_count = result.scalar()
            
            db.close()
            return {"success": True, "tables_count": tables_count}
            
        except Exception as e:
            return {"success": False, "error": str(e)[:100]}
    
    # Use a 3-second timeout for health check
    try:
        with ThreadPoolExecutor() as executor:
            future = executor.submit(simple_db_test)
            result = future.result(timeout=3)
            
        if result["success"]:
            return {
                "is_healthy": True,
                "database_connected": True,
                "tables_count": result["tables_count"],
                "status": "connected",
                "message": "Database is healthy and responsive"
            }
        else:
            return {
                "is_healthy": False, 
                "database_connected": False,
                "tables_count": 0,
                "status": "error",
                "error": result["error"],
                "message": "Database connection failed"
            }
            
    except FutureTimeoutError:
        return {
            "is_healthy": False,
            "database_connected": False,
            "tables_count": 0,
            "status": "scaling",
            "message": "🔄 Aurora Serverless is scaling - this is normal during cold starts",
            "recommendation": "Wait 30-60 seconds and try again"
        }
        
    except Exception as e:
        return {
            "is_healthy": False,
            "database_connected": False, 
            "tables_count": 0,
            "status": "error",
            "error": str(e)[:100],
            "message": "Health check failed"
        }


@router.post("/wake-db")
async def wake_database():
    """
    Wake up Aurora Serverless database without dependency injection.
    Use this endpoint to warm up the database before other operations.
    """
    try:
        from app.db.database import execute_with_retry
        import time
        
        start_time = time.time()
        
        def simple_wake_query(db_session):
            # Just test the connection
            result = db_session.execute(text("SELECT 1 as wake_test"))
            return result.scalar()
        
        result = execute_with_retry(simple_wake_query, max_retries=3)
        end_time = time.time()
        
        return {
            "status": "success",
            "message": "Database is now awake",
            "wake_time_seconds": round(end_time - start_time, 2),
            "result": result
        }
        
    except Exception as e:
        return {
            "status": "timeout",
            "message": "Database is still scaling. Aurora Serverless may take 30-60 seconds to wake up.",
            "error": str(e),
            "recommendation": "Try again in 30 seconds"
        }


@router.post("/run-migrations")
async def run_database_migrations(db: Session = Depends(get_db)):
    """
    Run database migrations directly from Lambda.
    This endpoint applies pending migrations to create missing tables.
    """
    try:
        from sqlalchemy import text
        
        # Check current state
        validation_result = SchemaValidator.validate_schema(db)
        
        if validation_result.get("is_valid", False):
            return {
                "status": "success",
                "message": "Database schema is already up to date",
                "validation": validation_result
            }
        
        missing_tables = validation_result.get("missing_tables", [])
        
        # If we have missing social tables, create them manually
        if "follows" in missing_tables or "content_likes" in missing_tables:
            
            # First, ensure alembic_version table exists
            try:
                db.execute(text("SELECT version_num FROM alembic_version LIMIT 1"))
                db.commit()
            except Exception as e:
                db.rollback()  # Rollback failed transaction
                
                # Create alembic_version table
                db.execute(text("""
                    CREATE TABLE alembic_version (
                        version_num VARCHAR(32) NOT NULL,
                        CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
                    )
                """))
                
                # Set initial version
                db.execute(text("INSERT INTO alembic_version (version_num) VALUES ('d46e7dd4403b')"))
                db.commit()
            
            # Create follows table if missing
            if "follows" in missing_tables:
                db.execute(text("""
                    CREATE TABLE follows (
                        id UUID NOT NULL DEFAULT gen_random_uuid(),
                        follower_id UUID NOT NULL,
                        following_id UUID NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (id),
                        FOREIGN KEY(follower_id) REFERENCES users (id) ON DELETE CASCADE,
                        FOREIGN KEY(following_id) REFERENCES users (id) ON DELETE CASCADE
                    )
                """))
                
                # Create indexes
                db.execute(text("CREATE INDEX ix_follows_follower_id ON follows (follower_id)"))
                db.execute(text("CREATE INDEX ix_follows_following_id ON follows (following_id)"))
                db.execute(text("CREATE UNIQUE INDEX ix_follows_follower_following ON follows (follower_id, following_id)"))
                
                logger.info("Created follows table with indexes")
            
            # Create content_likes table if missing  
            if "content_likes" in missing_tables:
                db.execute(text("""
                    CREATE TABLE content_likes (
                        id UUID NOT NULL DEFAULT gen_random_uuid(),
                        user_id UUID NOT NULL,
                        content_id UUID NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (id),
                        FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE,
                        FOREIGN KEY(content_id) REFERENCES content (id) ON DELETE CASCADE
                    )
                """))
                
                # Create indexes
                db.execute(text("CREATE INDEX ix_content_likes_user_id ON content_likes (user_id)"))
                db.execute(text("CREATE INDEX ix_content_likes_content_id ON content_likes (content_id)"))
                db.execute(text("CREATE UNIQUE INDEX ix_content_likes_user_content ON content_likes (user_id, content_id)"))
                
                logger.info("Created content_likes table with indexes")
            
            # Update alembic version to latest
            db.execute(text("UPDATE alembic_version SET version_num = 'add_social_features'"))
            db.commit()
            
            logger.info("Migration completed successfully")
            
            # Re-validate schema
            new_validation = SchemaValidator.validate_schema(db)
            
            return {
                "status": "success",
                "message": "Database migrations applied successfully",
                "created_tables": missing_tables,
                "validation": new_validation
            }
        
        else:
            return {
                "status": "no_action",
                "message": "No recognized migrations to apply",
                "validation": validation_result
            }
            
    except Exception as e:
        logger.error(f"Migration error: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Migration failed: {str(e)}"
        )


@router.post("/auth/sso")
async def sso_auth_with_db(firebase_user_data: dict, db: Session = Depends(get_db)):
    """
    Database SSO Authentication - Takes verified Firebase user data
    Accepts output from /auth/sso endpoint and creates/authenticates user in database
    No internet access needed - works with already-verified Firebase user data
    """
    try:
        from app.services.auth_service import AuthService
        
        # Extract Firebase user data (from /auth/sso endpoint output)
        uid = firebase_user_data.get("uid")
        email = firebase_user_data.get("email")
        name = firebase_user_data.get("name", "")
        picture = firebase_user_data.get("picture", "")
        provider = firebase_user_data.get("provider", "firebase")
        email_verified = firebase_user_data.get("email_verified", False)
        additional_details = firebase_user_data.get("additional_details", {})
        
        if not uid:
            raise HTTPException(
                status_code=400,
                detail="uid is required (Firebase user ID)"
            )
        
        if not email:
            raise HTTPException(
                status_code=400,
                detail="email is required"
            )
        
        # Create Firebase user dict for auth service
        firebase_user = {
            "firebase_uid": uid,
            "id": uid,
            "email": email,
            "name": name,
            "picture": picture,
            "provider": provider,
            "email_verified": email_verified
        }
        
        # Create or get user from database
        user, is_new = await AuthService.create_or_get_firebase_user(
            db, 
            firebase_user, 
            additional_details
        )
        
        # Generate tokens
        tokens = AuthService.generate_tokens(user)
        
        return {
            "success": True,
            "access_token": tokens["access_token"],
            "refresh_token": tokens["refresh_token"],
            "token_type": "bearer",
            "user": {
                "id": str(user.id),
                "email": user.email,
                "username": user.username,
                "signup_username": user.signup_username,
                "is_verified": user.is_verified,
                "created_at": user.created_at.isoformat() if user.created_at else None
            },
            "is_new_user": is_new,
            "firebase_data": {
                "uid": uid,
                "provider": provider,
                "email_verified": email_verified
            }
        }
        
    except Exception as e:
        logger.error(f"Database SSO authentication error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Database SSO authentication failed: {str(e)}"
        )