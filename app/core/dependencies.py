from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError, TimeoutError
from jose import JWTError
from app.db.database import get_db, execute_with_retry
from app.core.security import decode_token
from app.models.user import User, AuthUser, AdminUser
from typing import Optional
import logging
import time

logger = logging.getLogger(__name__)

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    Dependency to get the current authenticated user from JWT token with retry logic
    """
    token = credentials.credentials
    
    # Decode JWT token with retry logic for cold starts
    payload = await decode_jwt_with_retry(token)
    
    # Check token type
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Get user with database retry logic
    user = await get_user_with_retry(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return user


async def decode_jwt_with_retry(token: str, max_retries: int = 3) -> dict:
    """Decode JWT with retry logic for environment variable loading issues"""
    last_error = None
    
    for attempt in range(max_retries):
        try:
            import os
            from jose import jwt, JWTError
            
            # Get environment variables with fallback
            secret_key = os.environ.get('SECRET_KEY')
            algorithm = os.environ.get('ALGORITHM', 'HS256')
            
            # Handle case where environment might not be loaded yet
            if not secret_key:
                if attempt == 0:
                    logger.warning("SECRET_KEY not found in environment, retrying...")
                    time.sleep(0.1)  # Brief delay for env vars to load
                    continue
                else:
                    # Use fallback after retries
                    secret_key = 'fallback-secret-key-for-development'
                    logger.warning("Using fallback SECRET_KEY")
            
            payload = jwt.decode(token, secret_key, algorithms=[algorithm])
            return payload
            
        except JWTError as e:
            last_error = e
            if attempt < max_retries - 1:
                logger.warning(f"JWT decode attempt {attempt + 1} failed, retrying...")
                time.sleep(0.1 * (attempt + 1))  # Incremental backoff
            continue
        except Exception as e:
            logger.error(f"Unexpected error decoding JWT: {e}")
            last_error = e
            break
    
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_user_with_retry(db: Session, user_id: str, max_retries: int = 3) -> Optional[User]:
    """Get user from database with retry logic for connection issues"""
    def query_user(db_session):
        return db_session.query(User).filter(User.id == user_id).first()
    
    try:
        # Use existing database retry logic
        return execute_with_retry(query_user, max_retries=max_retries)
    except (OperationalError, TimeoutError) as e:
        logger.error(f"Database connection failed during user lookup: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database temporarily unavailable, please retry"
        )
    except Exception as e:
        logger.error(f"Unexpected error during user lookup: {e}")
        return None


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Dependency to ensure the user is active
    """
    if not current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please verify your email first"
        )
    return current_user


async def get_optional_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """
    Optional authentication - returns None if no valid token
    """
    if not credentials:
        return None
    
    try:
        return await get_current_user(credentials, db)
    except HTTPException:
        return None


async def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> AdminUser:
    """
    Dependency to get the current authenticated admin from JWT token
    """
    token = credentials.credentials
    
    # Decode JWT token
    payload = await decode_jwt_with_retry(token)
    
    # Check token type
    if payload.get("type") != "admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type - admin access required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    admin_id = payload.get("sub")
    if admin_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Get admin with database retry logic
    admin = await get_admin_with_retry(db, admin_id)
    if admin is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Admin not found"
        )
    
    if not admin.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin account is deactivated"
        )
    
    return admin


async def get_admin_with_retry(db: Session, admin_id: str, max_retries: int = 3) -> Optional[AdminUser]:
    """Get admin from database with retry logic for connection issues"""
    def query_admin(db_session):
        return db_session.query(AdminUser).filter(AdminUser.id == admin_id).first()
    
    try:
        return execute_with_retry(query_admin, max_retries=max_retries)
    except (OperationalError, TimeoutError) as e:
        logger.error(f"Database connection failed during admin lookup: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database temporarily unavailable, please retry"
        )
    except Exception as e:
        logger.error(f"Unexpected error during admin lookup: {e}")
        return None


def require_permission(permission: str):
    """
    Dependency factory for requiring specific admin permissions
    """
    def permission_dependency(current_admin: AdminUser = Depends(get_current_admin)) -> AdminUser:
        from app.services.admin_service import AdminService
        
        if not AdminService.has_permission(current_admin, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission '{permission}' required"
            )
        return current_admin
    
    return permission_dependency


def require_role(*allowed_roles):
    """
    Dependency factory for requiring specific admin roles
    """
    def role_dependency(current_admin: AdminUser = Depends(get_current_admin)) -> AdminUser:
        if current_admin.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"One of these roles required: {', '.join(allowed_roles)}"
            )
        return current_admin
    
    return role_dependency