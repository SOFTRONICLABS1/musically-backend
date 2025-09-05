from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple
from jose import JWTError, jwt
from passlib.context import CryptContext
from app.core.config import settings
from app.core.secrets_manager import secrets_manager
import secrets
import string

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    # Only set default type if not already specified
    if "type" not in to_encode:
        to_encode["type"] = "access"
    
    # Get JWT secret - use environment variable directly if available (for VPC Lambda)
    import os
    if os.environ.get('AWS_LAMBDA_FUNCTION_NAME') and os.environ.get('SECRET_KEY'):
        jwt_secret = settings.SECRET_KEY
    else:
        jwt_secret = secrets_manager.get_jwt_secret()
    encoded_jwt = jwt.encode(to_encode, jwt_secret, algorithm=settings.ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: dict) -> str:
    """Create JWT refresh token"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire})
    # Only set default type if not already specified  
    if "type" not in to_encode:
        to_encode["type"] = "refresh"
    
    # Get JWT secret - use environment variable directly if available (for VPC Lambda)
    import os
    if os.environ.get('AWS_LAMBDA_FUNCTION_NAME') and os.environ.get('SECRET_KEY'):
        jwt_secret = settings.SECRET_KEY
    else:
        jwt_secret = secrets_manager.get_jwt_secret()
    encoded_jwt = jwt.encode(to_encode, jwt_secret, algorithm=settings.ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> Dict[str, Any]:
    """Decode and verify JWT token"""
    try:
        # Get JWT secret - use environment variable directly if available (for VPC Lambda)
        import os
        if os.environ.get('AWS_LAMBDA_FUNCTION_NAME') and os.environ.get('SECRET_KEY'):
            jwt_secret = settings.SECRET_KEY
        else:
            jwt_secret = secrets_manager.get_jwt_secret()
        payload = jwt.decode(token, jwt_secret, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against hashed password"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password"""
    return pwd_context.hash(password)


def generate_random_token(length: int = 32) -> str:
    """Generate a random token for email verification, password reset, etc."""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def validate_password_strength(password: str) -> Tuple[bool, str]:
    """
    Validate password strength
    Returns (is_valid, error_message)
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    
    if not any(char.isdigit() for char in password):
        return False, "Password must contain at least one digit"
    
    if not any(char.isupper() for char in password):
        return False, "Password must contain at least one uppercase letter"
    
    if not any(char.islower() for char in password):
        return False, "Password must contain at least one lowercase letter"
    
    special_chars = "!@#$%^&*()_+-=[]{}|;:,.<>?"
    if not any(char in special_chars for char in password):
        return False, "Password must contain at least one special character"
    
    return True, "Password is strong"