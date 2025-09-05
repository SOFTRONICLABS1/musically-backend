import firebase_admin
from firebase_admin import credentials, auth
from typing import Dict, Any, Optional
from app.core.config import settings
import logging
import json

logger = logging.getLogger(__name__)


class FirebaseService:
    _app = None
    _initialized = False
    
    @classmethod
    def initialize(cls):
        """Initialize Firebase Admin SDK"""
        if cls._initialized:
            return
            
        try:
            # Process private key - handle different formats
            private_key = settings.FIREBASE_PRIVATE_KEY
            if isinstance(private_key, str):
                # Handle escaped newlines
                if '\\n' in private_key:
                    private_key = private_key.replace('\\n', '\n')
                # Remove quotes if present
                private_key = private_key.strip('"\'')
                
            logger.info(f"Private key starts with: {private_key[:30]}...")
            logger.info(f"Private key ends with: {private_key[-30:]}")
            
            # Create service account key from environment variables
            service_account_key = {
                "type": "service_account",
                "project_id": settings.FIREBASE_PROJECT_ID,
                "private_key_id": settings.FIREBASE_PRIVATE_KEY_ID,
                "private_key": private_key,
                "client_email": settings.FIREBASE_CLIENT_EMAIL,
                "client_id": settings.FIREBASE_CLIENT_ID,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "client_x509_cert_url": settings.FIREBASE_CLIENT_X509_CERT_URL,
                "universe_domain": "googleapis.com"
            }
            
            # Initialize Firebase Admin
            cred = credentials.Certificate(service_account_key)
            cls._app = firebase_admin.initialize_app(cred)
            cls._initialized = True
            
            logger.info("Firebase Admin SDK initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Firebase Admin SDK: {e}")
            raise
    
    @classmethod
    def verify_firebase_token_sync(cls, id_token: str) -> Optional[Dict[str, Any]]:
        """
        Synchronous Firebase ID token verification
        """
        try:
            # Ensure Firebase is initialized
            cls.initialize()
            
            # Verify the ID token (this is a blocking network call)
            decoded_token = auth.verify_id_token(id_token)
            
            # Extract user information
            return {
                "uid": decoded_token.get("uid"),
                "email": decoded_token.get("email", ""),
                "email_verified": decoded_token.get("email_verified", False),
                "name": decoded_token.get("name", ""),
                "picture": decoded_token.get("picture", ""),
                "provider": decoded_token.get("firebase", {}).get("sign_in_provider", ""),
                "auth_time": decoded_token.get("auth_time"),
                "custom_claims": decoded_token.get("custom_claims", {})
            }
            
        except firebase_admin.auth.InvalidIdTokenError:
            logger.error("Invalid Firebase ID token")
            return None
        except firebase_admin.auth.ExpiredIdTokenError:
            logger.error("Expired Firebase ID token")
            return None
        except Exception as e:
            logger.error(f"Unexpected error verifying Firebase token: {e}")
            return None

    @classmethod
    async def verify_firebase_token(cls, id_token: str) -> Optional[Dict[str, Any]]:
        """
        Async wrapper for Firebase ID token verification
        This works with tokens from Firebase Auth (Google, Apple, Email/Password, etc.)
        """
        import asyncio
        import concurrent.futures
        
        # Run the synchronous Firebase call in a thread pool
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as pool:
            result = await loop.run_in_executor(pool, cls.verify_firebase_token_sync, id_token)
            return result
    
    @classmethod
    async def get_firebase_user(cls, uid: str) -> Optional[Dict[str, Any]]:
        """Get Firebase user by UID"""
        try:
            cls.initialize()
            
            user_record = auth.get_user(uid)
            
            return {
                "uid": user_record.uid,
                "email": user_record.email,
                "email_verified": user_record.email_verified,
                "display_name": user_record.display_name,
                "photo_url": user_record.photo_url,
                "provider_data": [
                    {
                        "provider_id": provider.provider_id,
                        "uid": provider.uid,
                        "email": provider.email,
                        "display_name": provider.display_name,
                        "photo_url": provider.photo_url
                    }
                    for provider in user_record.provider_data
                ],
                "metadata": {
                    "creation_timestamp": user_record.user_metadata.creation_timestamp,
                    "last_sign_in_timestamp": user_record.user_metadata.last_sign_in_timestamp,
                    "last_refresh_timestamp": user_record.user_metadata.last_refresh_timestamp
                }
            }
            
        except firebase_admin.auth.UserNotFoundError:
            logger.error(f"Firebase user not found: {uid}")
            return None
        except Exception as e:
            logger.error(f"Error getting Firebase user: {e}")
            return None
    
    @classmethod
    async def create_custom_token(cls, uid: str, additional_claims: Optional[Dict] = None) -> str:
        """Create custom Firebase token for a user"""
        try:
            cls.initialize()
            
            custom_token = auth.create_custom_token(uid, additional_claims)
            return custom_token.decode('utf-8')
            
        except Exception as e:
            logger.error(f"Error creating custom token: {e}")
            raise
    
    @classmethod
    async def revoke_refresh_tokens(cls, uid: str) -> bool:
        """Revoke all refresh tokens for a user (sign out from all devices)"""
        try:
            cls.initialize()
            
            auth.revoke_refresh_tokens(uid)
            return True
            
        except Exception as e:
            logger.error(f"Error revoking refresh tokens: {e}")
            return False


# Initialize Firebase on import
firebase_service = FirebaseService()