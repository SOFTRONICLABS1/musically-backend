from google.auth.transport import requests
from google.oauth2 import id_token
import jwt
import httpx
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from app.core.config import settings
from app.services.firebase_service import firebase_service
import logging
import json
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend

logger = logging.getLogger(__name__)


class GoogleOAuthService:
    @staticmethod
    async def verify_token(token: str, platform: str = "web") -> Optional[Dict[str, Any]]:
        """Verify Google ID token and return user info"""
        try:
            # Choose appropriate client ID based on platform
            if platform.lower() == "ios":
                client_id = settings.GOOGLE_IOS_CLIENT_ID
            else:
                client_id = settings.GOOGLE_CLIENT_ID
            
            # Verify the token with Google
            idinfo = id_token.verify_oauth2_token(
                token, 
                requests.Request(), 
                client_id
            )
            
            # Token is valid, return user info
            return {
                "id": idinfo["sub"],
                "email": idinfo["email"],
                "email_verified": idinfo.get("email_verified", False),
                "name": idinfo.get("name", ""),
                "picture": idinfo.get("picture", ""),
                "given_name": idinfo.get("given_name", ""),
                "family_name": idinfo.get("family_name", "")
            }
        except ValueError as e:
            logger.error(f"Google token verification failed: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error verifying Google token: {e}")
            return None


class AppleOAuthService:
    @staticmethod
    def _get_apple_public_keys():
        """Fetch Apple's public keys for token verification"""
        try:
            response = httpx.get("https://appleid.apple.com/auth/keys")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to fetch Apple public keys: {e}")
            return None
    
    @staticmethod
    def _decode_apple_token(token: str, keys: dict) -> Optional[Dict[str, Any]]:
        """Decode and verify Apple ID token"""
        try:
            # Get the header to find the key ID
            header = jwt.get_unverified_header(token)
            kid = header.get("kid")
            
            # Find the matching key
            key = None
            for k in keys.get("keys", []):
                if k["kid"] == kid:
                    key = k
                    break
            
            if not key:
                logger.error("No matching key found for Apple token")
                return None
            
            # Decode the token
            decoded = jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                audience=settings.APPLE_CLIENT_ID,
                options={"verify_exp": True}
            )
            
            return decoded
        except jwt.ExpiredSignatureError:
            logger.error("Apple token has expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.error(f"Invalid Apple token: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error decoding Apple token: {e}")
            return None
    
    @staticmethod
    async def verify_token(token: str, user_info: Optional[dict] = None) -> Optional[Dict[str, Any]]:
        """Verify Apple ID token and return user info"""
        try:
            # Fetch Apple's public keys
            keys = AppleOAuthService._get_apple_public_keys()
            if not keys:
                return None
            
            # Decode and verify the token
            decoded = AppleOAuthService._decode_apple_token(token, keys)
            if not decoded:
                return None
            
            # Extract user info
            result = {
                "id": decoded["sub"],
                "email": decoded.get("email", ""),
                "email_verified": decoded.get("email_verified", False),
            }
            
            # Apple only provides name on first authorization
            if user_info:
                result["name"] = f"{user_info.get('firstName', '')} {user_info.get('lastName', '')}".strip()
                result["given_name"] = user_info.get("firstName", "")
                result["family_name"] = user_info.get("lastName", "")
            
            return result
        except Exception as e:
            logger.error(f"Unexpected error verifying Apple token: {e}")
            return None
    
    @staticmethod
    def generate_client_secret() -> str:
        """
        Generate client secret for Apple Sign In
        This is needed for server-to-server communication with Apple
        """
        try:
            # Load the private key
            with open(settings.APPLE_PRIVATE_KEY_PATH, 'r') as f:
                private_key = f.read()
            
            # Create the JWT
            headers = {
                "kid": settings.APPLE_KEY_ID,
                "alg": "ES256"
            }
            
            payload = {
                "iss": settings.APPLE_TEAM_ID,
                "iat": datetime.utcnow(),
                "exp": datetime.utcnow() + timedelta(days=180),
                "aud": "https://appleid.apple.com",
                "sub": settings.APPLE_CLIENT_ID
            }
            
            client_secret = jwt.encode(
                payload,
                private_key,
                algorithm="ES256",
                headers=headers
            )
            
            return client_secret
        except Exception as e:
            logger.error(f"Failed to generate Apple client secret: {e}")
            return None


class FirebaseOAuthService:
    @staticmethod
    async def verify_firebase_token(token: str) -> Optional[Dict[str, Any]]:
        """
        Verify Firebase ID token (supports Google, Apple, Email/Password, etc.)
        This is the recommended approach for Firebase Auth integration
        """
        try:
            # Use Firebase Admin SDK to verify token
            firebase_user = await firebase_service.verify_firebase_token(token)
            
            if not firebase_user:
                return None
            
            # Standardize the response format
            return {
                "id": firebase_user.get("uid"),
                "email": firebase_user.get("email", ""),
                "email_verified": firebase_user.get("email_verified", False),
                "name": firebase_user.get("name", ""),
                "picture": firebase_user.get("picture", ""),
                "provider": firebase_user.get("provider", "firebase"),
                "firebase_uid": firebase_user.get("uid"),
                "auth_time": firebase_user.get("auth_time"),
                "custom_claims": firebase_user.get("custom_claims", {})
            }
            
        except Exception as e:
            logger.error(f"Firebase token verification failed: {e}")
            return None
    
    @staticmethod
    async def get_firebase_user_details(uid: str) -> Optional[Dict[str, Any]]:
        """Get additional Firebase user details by UID"""
        try:
            return await firebase_service.get_firebase_user(uid)
        except Exception as e:
            logger.error(f"Failed to get Firebase user details: {e}")
            return None
    
    @staticmethod
    async def revoke_user_tokens(uid: str) -> bool:
        """Revoke all Firebase tokens for a user (sign out from all devices)"""
        try:
            return await firebase_service.revoke_refresh_tokens(uid)
        except Exception as e:
            logger.error(f"Failed to revoke Firebase tokens: {e}")
            return False