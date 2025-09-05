from pydantic import BaseModel, validator
from typing import Optional, List
from datetime import datetime
from uuid import UUID
from enum import Enum


class AdminRole(str, Enum):
    SUPER_ADMIN = "super_admin"
    CONTENT_MODERATOR = "content_moderator"
    USER_MANAGER = "user_manager"
    ANALYTICS_VIEWER = "analytics_viewer"


class AdminLoginRequest(BaseModel):
    email: str
    password: str


class AdminTokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    admin: 'AdminResponse'


class AdminResponse(BaseModel):
    id: UUID
    email: str
    username: str
    role: AdminRole
    permissions: Optional[List[str]] = None
    is_active: bool
    last_login: Optional[datetime] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class AdminCreateRequest(BaseModel):
    email: str
    username: str
    password: str
    role: AdminRole = AdminRole.CONTENT_MODERATOR
    permissions: Optional[List[str]] = None


class AdminUpdateRequest(BaseModel):
    email: Optional[str] = None
    username: Optional[str] = None
    role: Optional[AdminRole] = None
    permissions: Optional[List[str]] = None
    is_active: Optional[bool] = None


class AdminListResponse(BaseModel):
    admins: List[AdminResponse]
    total: int
    page: int
    per_page: int
    total_pages: int


# Update forward references
AdminTokenResponse.model_rebuild()