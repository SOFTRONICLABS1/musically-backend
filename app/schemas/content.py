from pydantic import BaseModel, Field, validator, HttpUrl
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from uuid import UUID
from enum import Enum


class ContentType(str, Enum):
    MEDIA_FILE = "media_file"
    SOCIAL_LINK = "social_link" 
    NOTES_ONLY = "notes_only"


class MediaType(str, Enum):
    AUDIO = "audio"
    VIDEO = "video"


class SocialPlatform(str, Enum):
    YOUTUBE = "youtube"
    FACEBOOK = "facebook"
    INSTAGRAM = "instagram"
    LINKEDIN = "linkedin"
    TIKTOK = "tiktok"
    TWITTER = "twitter"


class AccessType(str, Enum):
    FREE = "free"
    SUBSCRIBERS_ONLY = "subscribers_only"
    PLAYLIST_ONLY = "playlist_only"


class ContentBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    content_type: ContentType
    
    # Media file fields
    media_type: Optional[MediaType] = None
    
    # Social media link fields
    social_url: Optional[HttpUrl] = None
    social_platform: Optional[SocialPlatform] = None
    
    # Musical content
    notes_data: Optional[Dict[str, Any]] = None
    tempo: Optional[int] = Field(None, ge=30, le=300)  # BPM range
    
    # Access and visibility
    is_public: bool = True
    access_type: AccessType = AccessType.FREE
    tags: Optional[List[str]] = Field(None, max_items=10)
    
    @validator('tags')
    def validate_tags(cls, v):
        if v:
            # Clean and validate tags
            cleaned_tags = []
            for tag in v:
                if isinstance(tag, str) and len(tag.strip()) > 0:
                    cleaned_tag = tag.strip().lower()[:50]  # Max 50 chars per tag
                    if cleaned_tag not in cleaned_tags:
                        cleaned_tags.append(cleaned_tag)
            return cleaned_tags[:10]  # Max 10 tags
        return v
    
    @validator('social_platform')
    def validate_social_platform(cls, v, values):
        content_type = values.get('content_type')
        social_url = values.get('social_url')
        
        if content_type == ContentType.SOCIAL_LINK:
            if not social_url:
                raise ValueError('social_url is required when content_type is social_link')
            if not v:
                raise ValueError('social_platform is required when content_type is social_link')
        return v
    
    @validator('media_type')
    def validate_media_type(cls, v, values):
        content_type = values.get('content_type')
        
        if content_type == ContentType.MEDIA_FILE and not v:
            raise ValueError('media_type is required when content_type is media_file')
        return v


class ContentCreate(ContentBase):
    game_ids: Optional[List[UUID]] = Field(None, max_items=10)


class ContentUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    
    # Social media link fields (can be updated)
    social_url: Optional[HttpUrl] = None
    social_platform: Optional[SocialPlatform] = None
    
    # Musical content
    notes_data: Optional[Dict[str, Any]] = None
    tempo: Optional[int] = Field(None, ge=30, le=300)
    
    # Access and visibility
    is_public: Optional[bool] = None
    access_type: Optional[AccessType] = None
    tags: Optional[List[str]] = Field(None, max_items=10)
    
    @validator('tags')
    def validate_tags(cls, v):
        if v:
            cleaned_tags = []
            for tag in v:
                if isinstance(tag, str) and len(tag.strip()) > 0:
                    cleaned_tag = tag.strip().lower()[:50]
                    if cleaned_tag not in cleaned_tags:
                        cleaned_tags.append(cleaned_tag)
            return cleaned_tags[:10]
        return v


class ContentResponse(BaseModel):
    id: UUID
    user_id: UUID
    signup_username: Optional[str] = None  # User's display name
    title: str
    description: Optional[str]
    
    # Content type and location
    content_type: ContentType
    download_url: Optional[str]  # Pre-signed download URL for media files
    media_type: Optional[MediaType]
    social_url: Optional[str]
    social_platform: Optional[SocialPlatform]
    
    # Musical content data
    notes_data: Optional[Dict[str, Any]]
    tempo: Optional[int]
    
    # Access and visibility
    is_public: bool
    access_type: AccessType
    tags: Optional[List[str]]
    
    # Metrics
    play_count: int
    avg_score: Optional[float]
    
    # Timestamps
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v)
        }


class ContentListResponse(BaseModel):
    contents: List[ContentResponse]
    total: int
    page: int
    per_page: int
    total_pages: int


class ContentFilters(BaseModel):
    content_type: Optional[ContentType] = None
    media_type: Optional[MediaType] = None
    social_platform: Optional[SocialPlatform] = None
    access_type: Optional[AccessType] = None
    is_public: Optional[bool] = None
    tags: Optional[List[str]] = None
    search: Optional[str] = Field(None, max_length=100)  # Search in title/description
    
    # Pagination
    page: int = Field(1, ge=1)
    per_page: int = Field(20, ge=1, le=100)


class FileUploadResponse(BaseModel):
    url: str
    file_name: str
    file_size: int
    content_type: str


class S3PresignedUploadResponse(BaseModel):
    upload_url: str
    fields: Dict[str, str]
    s3_key: str
    bucket: str
    expires_in: int
    file_url: str
    
    
class S3PresignedDownloadResponse(BaseModel):
    download_url: str
    expires_in: int
    file_name: Optional[str]
    content_type: Optional[str]
    file_size: Optional[int]


class SocialLinkValidationResponse(BaseModel):
    is_valid: bool
    platform: Optional[SocialPlatform]
    title: Optional[str]
    description: Optional[str]
    thumbnail_url: Optional[str]
    error_message: Optional[str]


class MediaUploadRequest(BaseModel):
    filename: str
    content_type: str
    file_size: int = Field(..., gt=0, le=104857600)  # Max 100MB
    
    @validator('content_type')
    def validate_content_type(cls, v):
        allowed_types = {
            # Audio
            "audio/mpeg", "audio/wav", "audio/ogg", "audio/m4a", "audio/aac", "audio/mp3",
            # Video  
            "video/mp4", "video/avi", "video/mov", "video/wmv", "video/webm", "video/quicktime"
        }
        
        if v not in allowed_types:
            raise ValueError(f"Unsupported content type: {v}")
        return v