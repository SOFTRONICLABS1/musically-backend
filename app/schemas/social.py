from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from uuid import UUID


class FollowResponse(BaseModel):
    id: UUID
    follower_id: UUID
    following_id: UUID
    created_at: datetime
    
    class Config:
        from_attributes = True


class UserFollowInfo(BaseModel):
    id: UUID
    username: Optional[str]
    signup_username: Optional[str]
    profile_image_url: Optional[str]
    bio: Optional[str]
    is_verified: bool
    followed_at: datetime
    
    class Config:
        from_attributes = True


class FollowersListResponse(BaseModel):
    followers: List[UserFollowInfo]
    total: int
    page: int
    per_page: int
    total_pages: int


class FollowingListResponse(BaseModel):
    following: List[UserFollowInfo]
    total: int
    page: int
    per_page: int
    total_pages: int


class FollowStatsResponse(BaseModel):
    followers_count: int
    following_count: int


class LikeResponse(BaseModel):
    id: UUID
    user_id: UUID
    content_id: UUID
    created_at: datetime
    
    class Config:
        from_attributes = True


class ContentLikeInfo(BaseModel):
    id: UUID
    title: str
    description: Optional[str]
    content_type: str
    media_type: Optional[str]
    user_id: UUID
    username: Optional[str]
    liked_at: datetime
    
    class Config:
        from_attributes = True


class LikedContentListResponse(BaseModel):
    content: List[ContentLikeInfo]
    total: int
    page: int
    per_page: int
    total_pages: int


class ContentLikeStatsResponse(BaseModel):
    likes_count: int
    is_liked: bool  # Whether current user has liked this content