from sqlalchemy.orm import Session
from app.models.user import User, AuthUser
from app.schemas.auth import UserCreate, UserLogin
from app.core.security import verify_password, get_password_hash, create_access_token, create_refresh_token
from app.services.oauth_service import GoogleOAuthService, AppleOAuthService, FirebaseOAuthService
from app.services.hybrid_cache_service import hybrid_cache
from app.services.redis_service import CacheKeys
from typing import Optional, Tuple
from datetime import datetime
import uuid
import re
import logging
import hashlib

logger = logging.getLogger(__name__)


class AuthService:
    @staticmethod
    def get_user_by_email_cached(db: Session, email: str, auth_provider: str = "local") -> Optional[User]:
        """Get user by email with caching"""
        cache_key = CacheKeys.format_key(
            CacheKeys.USER_BY_EMAIL, 
            email=hashlib.md5(email.encode()).hexdigest()  # Hash email for privacy
        )
        
        cached_user = hybrid_cache.get(cache_key)
        if cached_user:
            logger.debug(f"Cache HIT for user email lookup")
            return User(**cached_user) if cached_user else None
        
        logger.debug(f"Cache MISS for user email lookup")
        
        # Query database
        auth_user = db.query(AuthUser).filter(
            AuthUser.email == email,
            AuthUser.auth_provider == auth_provider
        ).first()
        
        user = auth_user.user if auth_user else None
        
        # Cache result (including None results)
        if user:
                user_dict = {
                    'id': user.id,
                    'email': user.email,
                    'username': user.username,
                    'gender': user.gender,
                    'phone_number': user.phone_number,
                    'country_code': user.country_code,
                    'bio': user.bio,
                    'profile_image_url': user.profile_image_url,
                    'is_premium': user.is_premium,
                    'is_verified': user.is_verified,
                    'is_active': user.is_active,
                    'created_at': user.created_at,
                    'updated_at': user.updated_at
                }
                hybrid_cache.set(cache_key, user_dict, 300)  # 5 min cache
        else:
            hybrid_cache.set(cache_key, None, 60)  # Cache "not found" for 1 min
        
        return user
    
    @staticmethod
    def create_user(db: Session, user_data: UserCreate) -> Tuple[User, AuthUser]:
        """Create a new user with local authentication"""
        # Check if email already exists
        existing_auth = db.query(AuthUser).filter(
            AuthUser.email == user_data.email,
            AuthUser.auth_provider == "local"
        ).first()
        
        if existing_auth:
            raise ValueError("Email already registered")
        
        # Check if username already exists
        existing_user = db.query(User).filter(User.username == user_data.username).first()
        if existing_user:
            raise ValueError("Username already taken")
        
        # Create main user record
        user = User(
            email=user_data.email,
            username=user_data.username,
            gender=user_data.gender,
            phone_number=user_data.phone_number,
            country_code=user_data.country_code,
            bio=user_data.bio,
            profile_image_url=user_data.profile_image_url
        )
        db.add(user)
        db.flush()  # Get the user ID
        
        # Create auth record
        auth_user = AuthUser(
            user_id=user.id,
            auth_provider="local",
            email=user_data.email,
            password_hash=get_password_hash(user_data.password),
            is_email_verified=False
        )
        db.add(auth_user)
        db.commit()
        db.refresh(user)
        db.refresh(auth_user)
        
        return user, auth_user
    
    @staticmethod
    def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
        """Authenticate user with email and password (with caching for user lookup)"""
        # First check if we have this user cached
        user = AuthService.get_user_by_email_cached(db, email, "local")
        
        if not user:
            return None
        
        # Get auth record to verify password (not cached for security)
        auth_user = db.query(AuthUser).filter(
            AuthUser.email == email,
            AuthUser.auth_provider == "local"
        ).first()
        
        if not auth_user or not verify_password(password, auth_user.password_hash):
            return None
        
        # Update last login
        auth_user.last_login = datetime.utcnow()
        db.commit()
        
        # Invalidate user cache on successful login (in case of user data changes)
        email_hash = hashlib.md5(email.encode()).hexdigest()
        cache_key = CacheKeys.format_key(CacheKeys.USER_BY_EMAIL, email=email_hash)
        hybrid_cache.delete(cache_key)
        
        return auth_user.user
    
    @staticmethod
    async def authenticate_google_user(db: Session, id_token: str, additional_details: Optional[dict] = None, platform: str = "web") -> Tuple[User, bool]:
        """
        Authenticate or create user via Google OAuth
        Returns (user, is_new_user)
        """
        # Verify the Google token
        google_user = await GoogleOAuthService.verify_token(id_token, platform)
        if not google_user:
            raise ValueError("Invalid Google token")
        
        # Check if user exists
        auth_user = db.query(AuthUser).filter(
            AuthUser.provider_user_id == google_user["id"],
            AuthUser.auth_provider == "google"
        ).first()
        
        if auth_user:
            # Existing user - update last login and Google name
            auth_user.last_login = datetime.utcnow()
            
            # Update signup_username with latest name from Google if available
            if google_user.get("name"):
                auth_user.user.signup_username = google_user["name"]
            
            db.commit()
            return auth_user.user, False
        
        # Check if email is already used by another provider
        existing_auth = db.query(AuthUser).filter(
            AuthUser.email == google_user["email"]
        ).first()
        
        if existing_auth:
            # Email exists with different provider
            # You might want to link accounts here
            raise ValueError(f"Email already registered with {existing_auth.auth_provider} provider")
        
        # Create new user with enhanced details
        # Store the Google provided name as signup_username
        
        # Prepare user data with defaults
        user_data = {
            "email": google_user["email"],
            "username": None,  # Keep username blank initially
            "signup_username": google_user.get("name", ""),  # Store Google name here
            "gender": "not_specified",  # Default for OAuth users
            "profile_image_url": google_user.get("picture"),
            "is_verified": google_user.get("email_verified", False)
        }
        
        # Add additional details if provided
        if additional_details:
            # Map additional details to user fields
            if additional_details.get("phone_number"):
                user_data["phone_number"] = additional_details["phone_number"]
            if additional_details.get("country_code"):
                user_data["country_code"] = additional_details["country_code"]
            if additional_details.get("gender"):
                user_data["gender"] = additional_details["gender"]
            if additional_details.get("location"):
                user_data["location"] = additional_details["location"]
        
        user = User(**user_data)
        db.add(user)
        db.flush()
        
        auth_user = AuthUser(
            user_id=user.id,
            auth_provider="google",
            provider_user_id=google_user["id"],
            email=google_user["email"],
            is_email_verified=google_user.get("email_verified", False),
            last_login=datetime.utcnow()
        )
        db.add(auth_user)
        db.commit()
        db.refresh(user)
        
        return user, True
    
    @staticmethod
    async def authenticate_apple_user(db: Session, id_token: str, user_info: Optional[dict] = None) -> Tuple[User, bool]:
        """
        Authenticate or create user via Apple Sign In
        Returns (user, is_new_user)
        """
        # Verify the Apple token
        apple_user = await AppleOAuthService.verify_token(id_token, user_info)
        if not apple_user:
            raise ValueError("Invalid Apple token")
        
        # Check if user exists
        auth_user = db.query(AuthUser).filter(
            AuthUser.provider_user_id == apple_user["id"],
            AuthUser.auth_provider == "apple"
        ).first()
        
        if auth_user:
            # Existing user - update last login and Apple name
            auth_user.last_login = datetime.utcnow()
            
            # Update signup_username with latest name from Apple if available
            if apple_user.get("name"):
                auth_user.user.signup_username = apple_user["name"]
            
            db.commit()
            return auth_user.user, False
        
        # Check if email is already used by another provider
        if apple_user.get("email"):
            existing_auth = db.query(AuthUser).filter(
                AuthUser.email == apple_user["email"]
            ).first()
            
            if existing_auth:
                raise ValueError(f"Email already registered with {existing_auth.auth_provider} provider")
        
        # Create new user
        email = apple_user.get("email", f"{apple_user['id']}@privaterelay.appleid.com")
        
        user = User(
            email=email,
            username=None,  # Keep username blank initially
            signup_username=apple_user.get("name", ""),  # Store Apple name here
            gender="not_specified",  # Default for OAuth users
            is_verified=apple_user.get("email_verified", False)
        )
        db.add(user)
        db.flush()
        
        auth_user = AuthUser(
            user_id=user.id,
            auth_provider="apple",
            provider_user_id=apple_user["id"],
            email=email,
            is_email_verified=apple_user.get("email_verified", False),
            last_login=datetime.utcnow()
        )
        db.add(auth_user)
        db.commit()
        db.refresh(user)
        
        return user, True
    
    @staticmethod
    async def authenticate_firebase_user(
        db: Session, 
        id_token: str, 
        additional_details: Optional[dict] = None
    ) -> Tuple[User, bool]:
        """
        Authenticate or create user via Firebase Auth
        Supports Google, Apple, Email/Password, and other Firebase providers
        Returns (user, is_new_user)
        """
        # Verify the Firebase token
        firebase_user = await FirebaseOAuthService.verify_firebase_token(id_token)
        if not firebase_user:
            raise ValueError("Invalid Firebase token")
        
        firebase_uid = firebase_user["firebase_uid"]
        provider = firebase_user.get("provider", "firebase")
        
        # Check if user exists by Firebase UID
        auth_user = db.query(AuthUser).filter(
            AuthUser.provider_user_id == firebase_uid,
            AuthUser.auth_provider == "firebase"
        ).first()
        
        if auth_user:
            # Existing user - update last login
            auth_user.last_login = datetime.utcnow()
            
            # Update user info with latest from Firebase
            if firebase_user.get("name"):
                auth_user.user.signup_username = firebase_user["name"]
            if firebase_user.get("picture"):
                auth_user.user.profile_image_url = firebase_user["picture"]
            
            db.commit()
            return auth_user.user, False
        
        # Check if email is already used by another provider
        email = firebase_user.get("email")
        if email:
            existing_auth = db.query(AuthUser).filter(
                AuthUser.email == email,
                AuthUser.auth_provider != "firebase"
            ).first()
            
            if existing_auth:
                raise ValueError(f"Email already registered with {existing_auth.auth_provider} provider")
        
        # Create new user
        display_name = firebase_user.get("name", "")
        if not display_name and additional_details:
            display_name = additional_details.get("name", "")
        
        # Don't generate username for SSO users - keep it blank initially
        # Username should be set later by the user
        username = None
        
        user = User(
            email=email or "",
            username=username,  # Keep blank for SSO users
            signup_username=display_name,
            gender="not_specified",  # Default value since Firebase doesn't provide this
            profile_image_url=firebase_user.get("picture", ""),
            bio=additional_details.get("bio", "") if additional_details else ""
        )
        db.add(user)
        db.flush()
        
        # Create auth record
        auth_user = AuthUser(
            user_id=user.id,
            auth_provider="firebase",
            provider_user_id=firebase_uid,
            email=email or "",
            is_email_verified=firebase_user.get("email_verified", False),
            last_login=datetime.utcnow(),
            additional_data={
                "firebase_provider": provider,
                "auth_time": firebase_user.get("auth_time"),
                "custom_claims": firebase_user.get("custom_claims", {})
            }
        )
        db.add(auth_user)
        db.commit()
        db.refresh(user)
        
        return user, True
    
    @staticmethod
    def _generate_unique_username(db: Session, base_name: str) -> str:
        """Generate a unique username from a base name"""
        # Clean the base name
        username = re.sub(r'[^a-zA-Z0-9_]', '', base_name.lower().replace(' ', '_'))
        
        if not username:
            username = "user"
        
        # Truncate if too long
        if len(username) > 90:
            username = username[:90]
        
        # Check if username exists and add numbers if needed
        original = username
        counter = 1
        while db.query(User).filter(User.username == username).first():
            username = f"{original}_{counter}"
            counter += 1
        
        return username
    
    @staticmethod
    async def create_or_get_firebase_user(
        db: Session, 
        firebase_user: dict, 
        additional_details: Optional[dict] = None
    ) -> Tuple[User, bool]:
        """
        Create or get user from database using verified Firebase user data
        No internet access needed - works with already-verified data
        Returns (user, is_new_user)
        """
        firebase_uid = firebase_user["firebase_uid"]
        provider = firebase_user.get("provider", "firebase")
        
        # Check if user exists by Firebase UID
        auth_user = db.query(AuthUser).filter(
            AuthUser.provider_user_id == firebase_uid,
            AuthUser.auth_provider == "firebase"
        ).first()
        
        if auth_user:
            # Existing user - update last login and info
            auth_user.last_login = datetime.utcnow()
            
            # Update user info with latest from Firebase
            if firebase_user.get("name"):
                auth_user.user.signup_username = firebase_user["name"]
            if firebase_user.get("picture"):
                auth_user.user.profile_image_url = firebase_user["picture"]
            
            db.commit()
            return auth_user.user, False
        
        # Check if email is already used by another provider
        email = firebase_user.get("email")
        if email:
            existing_auth = db.query(AuthUser).filter(
                AuthUser.email == email,
                AuthUser.auth_provider != "firebase"
            ).first()
            
            if existing_auth:
                raise ValueError(f"Email already registered with {existing_auth.auth_provider} provider")
        
        # Create new user
        display_name = firebase_user.get("name", "")
        
        # Don't generate username for SSO users - keep it blank initially
        # Username should be set later by the user
        username = None
        
        # Create user - note: gender is required but we don't have it from Firebase
        user = User(
            email=email or "",
            username=username,  # Keep blank for SSO users
            signup_username=display_name,
            gender="not_specified",  # Default value since Firebase doesn't provide this
            profile_image_url=firebase_user.get("picture", "")
        )
        db.add(user)
        db.flush()
        
        # Create auth record
        auth_user = AuthUser(
            user_id=user.id,
            auth_provider="firebase",
            provider_user_id=firebase_uid,
            email=email or "",
            is_email_verified=firebase_user.get("email_verified", False),
            last_login=datetime.utcnow()
        )
        db.add(auth_user)
        db.commit()
        
        return user, True
    
    @staticmethod
    def generate_tokens(user: User) -> dict:
        """Generate access and refresh tokens for a user"""
        access_token = create_access_token(data={"sub": str(user.id)})
        refresh_token = create_refresh_token(data={"sub": str(user.id)})
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        }