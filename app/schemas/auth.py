from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List
from datetime import datetime
from uuid import UUID


class UserBase(BaseModel):
    email: EmailStr
    username: Optional[str] = Field(None, min_length=3, max_length=100)
    gender: str = Field(..., max_length=20)
    phone_number: Optional[str] = None
    country_code: Optional[str] = None


class UserCreate(UserBase):
    username: str = Field(..., min_length=3, max_length=100)  # Required for regular signup
    password: str = Field(..., min_length=8)
    
    @validator('username')
    def username_alphanumeric(cls, v):
        # Allow alphanumeric characters, underscores, dots, and spaces
        allowed_chars = v.replace('_', '').replace('.', '').replace(' ', '')
        assert allowed_chars.isalnum(), 'Username must be alphanumeric (underscores, dots, and spaces allowed)'
        return v


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class GoogleAuthRequest(BaseModel):
    id_token: str  # Google ID token from frontend
    additional_details: Optional[dict] = None  # Optional additional user details for profile setup
    platform: Optional[str] = "web"  # Platform: "web", "ios", "android"


class AppleAuthRequest(BaseModel):
    id_token: str  # Apple ID token from frontend
    user: Optional[dict] = None  # User info from Apple (first time only)


class SSORequest(BaseModel):
    id_token: str  # Firebase ID token from frontend (supports Google, Apple, Email/Password, etc.)
    additional_details: Optional[dict] = None  # Optional additional user details for profile setup


class FirebaseUserResponse(BaseModel):
    uid: str
    email: str
    email_verified: bool
    name: str
    picture: str
    provider: str
    additional_details: dict = {}


class UserResponse(BaseModel):
    id: UUID
    email: str
    username: Optional[str] = None
    signup_username: Optional[str] = None
    gender: str
    phone_number: Optional[str]
    country_code: Optional[str]
    bio: Optional[str]
    profile_image_url: Optional[str]
    instruments_taught: Optional[List[str]] = None
    years_of_experience: Optional[float] = None
    teaching_style: Optional[str] = None
    location: Optional[str] = None
    is_verified: bool
    subscription_tier: str
    total_subscribers: int
    total_content_created: int
    created_at: datetime
    
    @validator('instruments_taught', pre=True)
    def parse_instruments_taught(cls, v):
        if isinstance(v, str):
            import json
            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return []
        return v
    
    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse
    is_new_user: Optional[bool] = None  # True for new signups, False for existing users, None for regular login


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8)


class UpdateProfile(BaseModel):
    bio: Optional[str] = None
    profile_image_url: Optional[str] = None
    instruments_taught: Optional[List[str]] = None
    years_of_experience: Optional[float] = Field(None, ge=0, le=100)
    teaching_style: Optional[str] = None
    location: Optional[str] = None


class MessageResponse(BaseModel):
    message: str
    success: bool = True


class UsernameCheckRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=100)
    
    @validator('username')
    def username_alphanumeric(cls, v):
        # Allow alphanumeric characters, underscores, dots, and spaces
        allowed_chars = v.replace('_', '').replace('.', '').replace(' ', '')
        assert allowed_chars.isalnum(), 'Username must be alphanumeric (underscores, dots, and spaces allowed)'
        return v


class UsernameCheckResponse(BaseModel):
    available: bool
    message: str


class UpdateUsernameRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=100)
    
    @validator('username')
    def username_alphanumeric(cls, v):
        # Allow alphanumeric characters, underscores, dots, and spaces
        allowed_chars = v.replace('_', '').replace('.', '').replace(' ', '')
        assert allowed_chars.isalnum(), 'Username must be alphanumeric (underscores, dots, and spaces allowed)'
        return v


class UpdatePhoneRequest(BaseModel):
    phone_number: Optional[str] = Field(None, min_length=4, max_length=20)
    country_code: Optional[str] = Field(None, min_length=1, max_length=5)
    
    @validator('phone_number')
    def validate_phone_number(cls, v):
        if v is None:
            return None
            
        # Remove spaces and non-digit characters
        cleaned = ''.join(filter(str.isdigit, v))
        
        if not cleaned:
            return None
            
        # Validate phone number length (typically 4-15 digits without country code)
        if len(cleaned) < 4 or len(cleaned) > 15:
            raise ValueError('Phone number must be between 4 and 15 digits')
            
        return cleaned
    
    @validator('country_code')
    def validate_country_code(cls, v):
        if v is None:
            return None
            
        # Clean country code - remove spaces and non-essential characters
        cleaned = v.strip()
        
        # Ensure it starts with + or is just digits
        if cleaned.startswith('+'):
            code_part = cleaned[1:]
        else:
            code_part = cleaned
            cleaned = '+' + cleaned  # Add + if not present
        
        # Validate that the rest is digits only
        if not code_part.isdigit():
            raise ValueError('Country code must contain only digits (optionally prefixed with +)')
        
        # Validate country code length (1-4 digits typically)
        if len(code_part) < 1 or len(code_part) > 4:
            raise ValueError('Country code must be 1-4 digits')
        
        return cleaned
    
    @validator('country_code', always=True)
    def validate_both_fields(cls, v, values):
        phone_number = values.get('phone_number')
        
        # Both must be provided or both must be None/empty
        if (phone_number and not v) or (not phone_number and v):
            raise ValueError('Both phone_number and country_code must be provided together or both must be empty')
        
        return v