from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.schemas.admin import (
    AdminLoginRequest, AdminTokenResponse, AdminResponse, 
    AdminCreateRequest, AdminUpdateRequest, AdminListResponse
)
from app.schemas.auth import MessageResponse, UserResponse
from app.schemas.content import ContentResponse, ContentListResponse, ContentUpdate
from pydantic import BaseModel
from typing import List
from app.services.admin_service import AdminService
from app.core.security import create_access_token, create_refresh_token
from app.core.dependencies import get_current_admin, require_permission
from app.models.user import AdminUser, User, Content
from app.services.content_service import ContentService
from uuid import UUID
from typing import List
import logging

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Admin"])


# Admin response schemas
class UserListResponse(BaseModel):
    users: List[UserResponse]
    total: int
    page: int
    per_page: int
    total_pages: int


@router.post("/login", response_model=AdminTokenResponse)
async def admin_login(request: AdminLoginRequest, db: Session = Depends(get_db)):
    """
    Admin login
    """
    try:
        admin = AdminService.authenticate_admin(db, request.email, request.password)
        
        if not admin:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        # Create tokens
        access_token = create_access_token(data={"sub": str(admin.id), "type": "admin"})
        refresh_token = create_refresh_token(data={"sub": str(admin.id), "type": "admin"})
        
        return AdminTokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            admin=AdminResponse.from_orm(admin)
        )
        
    except Exception as e:
        logger.error(f"Admin login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during login"
        )


@router.get("/me", response_model=AdminResponse)
async def get_current_admin_info(current_admin: AdminUser = Depends(get_current_admin)):
    """
    Get current admin information
    """
    return AdminResponse.from_orm(current_admin)


@router.post("/create", response_model=AdminResponse)
async def create_admin(
    request: AdminCreateRequest,
    current_admin: AdminUser = Depends(require_permission("manage_admins")),
    db: Session = Depends(get_db)
):
    """
    Create a new admin user (requires super admin or manage_admins permission)
    """
    try:
        admin = AdminService.create_admin(db, request, current_admin.id)
        return AdminResponse.from_orm(admin)
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Create admin error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while creating admin"
        )


@router.get("/list", response_model=AdminListResponse)
async def list_admins(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_admin: AdminUser = Depends(require_permission("view_admins")),
    db: Session = Depends(get_db)
):
    """
    List all admin users
    """
    try:
        admins, total = AdminService.get_all_admins(db, page, per_page)
        total_pages = (total + per_page - 1) // per_page
        
        return AdminListResponse(
            admins=[AdminResponse.from_orm(admin) for admin in admins],
            total=total,
            page=page,
            per_page=per_page,
            total_pages=total_pages
        )
        
    except Exception as e:
        logger.error(f"List admins error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while fetching admins"
        )


# User Management Endpoints for Admins
@router.get("/users", response_model=UserListResponse)
async def admin_list_users(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: str = Query(None),
    current_admin: AdminUser = Depends(require_permission("view_users")),
    db: Session = Depends(get_db)
):
    """
    Admin endpoint to list all users with pagination and search
    """
    try:
        query = db.query(User)
        
        # Apply search filter if provided
        if search:
            query = query.filter(
                (User.email.ilike(f"%{search}%")) |
                (User.username.ilike(f"%{search}%"))
            )
        
        # Get total count
        total = query.count()
        
        # Apply pagination
        users = query.offset((page - 1) * per_page).limit(per_page).all()
        
        # Calculate total pages
        total_pages = (total + per_page - 1) // per_page
        
        return UserListResponse(
            users=[UserResponse.from_orm(user) for user in users],
            total=total,
            page=page,
            per_page=per_page,
            total_pages=total_pages
        )
        
    except Exception as e:
        logger.error(f"Admin list users error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while fetching users"
        )


@router.get("/users/{user_id}", response_model=UserResponse)
async def admin_get_user(
    user_id: UUID,
    current_admin: AdminUser = Depends(require_permission("view_users")),
    db: Session = Depends(get_db)
):
    """
    Admin endpoint to get user by ID
    """
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return UserResponse.from_orm(user)


@router.delete("/users/{user_id}", response_model=MessageResponse)
async def admin_delete_user(
    user_id: UUID,
    current_admin: AdminUser = Depends(require_permission("delete_users")),
    db: Session = Depends(get_db)
):
    """
    Admin endpoint to delete/deactivate user
    """
    try:
        user = db.query(User).filter(User.id == user_id).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # For safety, we'll deactivate rather than hard delete
        # You could add is_active field to User model for soft delete
        db.delete(user)
        db.commit()
        
        return MessageResponse(message="User deleted successfully")
        
    except Exception as e:
        logger.error(f"Admin delete user error: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while deleting user"
        )


# Content Management Endpoints for Admins
@router.get("/content", response_model=ContentListResponse)
async def admin_list_content(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: str = Query(None),
    current_admin: AdminUser = Depends(require_permission("view_content")),
    db: Session = Depends(get_db)
):
    """
    Admin endpoint to list all content with pagination and search
    """
    try:
        query = db.query(Content)
        
        # Apply search filter if provided
        if search:
            query = query.filter(
                (Content.title.ilike(f"%{search}%")) |
                (Content.description.ilike(f"%{search}%"))
            )
        
        # Get total count
        total = query.count()
        
        # Apply pagination and join with User table to get signup_username
        content_list = query.join(User).offset((page - 1) * per_page).limit(per_page).all()
        
        # Calculate total pages
        total_pages = (total + per_page - 1) // per_page
        
        # Convert content to response with user info
        content_responses = []
        for content in content_list:
            content_data = ContentService.content_to_response(content)
            content_data["signup_username"] = content.user.signup_username
            content_responses.append(ContentResponse(**content_data))
        
        return ContentListResponse(
            contents=content_responses,
            total=total,
            page=page,
            per_page=per_page,
            total_pages=total_pages
        )
        
    except Exception as e:
        logger.error(f"Admin list content error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while fetching content"
        )


@router.get("/content/{content_id}", response_model=ContentResponse)
async def admin_get_content(
    content_id: UUID,
    current_admin: AdminUser = Depends(require_permission("view_content")),
    db: Session = Depends(get_db)
):
    """
    Admin endpoint to get content by ID
    """
    content = db.query(Content).join(User).filter(Content.id == content_id).first()
    
    if not content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Content not found"
        )
    
    content_data = ContentService.content_to_response(content)
    content_data["signup_username"] = content.user.signup_username
    return ContentResponse(**content_data)


@router.put("/content/{content_id}", response_model=ContentResponse)
async def admin_update_content(
    content_id: UUID,
    update_data: ContentUpdate,
    current_admin: AdminUser = Depends(require_permission("edit_content")),
    db: Session = Depends(get_db)
):
    """
    Admin endpoint to update content
    """
    try:
        content = db.query(Content).filter(Content.id == content_id).first()
        
        if not content:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Content not found"
            )
        
        # Update content using existing service
        updated_content = ContentService.update_content(db, content_id, content.user_id, update_data)
        
        if not updated_content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to update content"
            )
        
        return ContentResponse(**ContentService.content_to_response(updated_content))
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin update content error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while updating content"
        )


@router.delete("/content/{content_id}", response_model=MessageResponse)
async def admin_delete_content(
    content_id: UUID,
    current_admin: AdminUser = Depends(require_permission("delete_content")),
    db: Session = Depends(get_db)
):
    """
    Admin endpoint to delete content
    """
    try:
        content = db.query(Content).filter(Content.id == content_id).first()
        
        if not content:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Content not found"
            )
        
        # Use existing service to delete content
        success = ContentService.delete_content(db, content_id, content.user_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to delete content"
            )
        
        return MessageResponse(message="Content deleted successfully")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin delete content error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while deleting content"
        )


# Admin CRUD Endpoints (must be at the end due to {admin_id} path parameter)
@router.get("/{admin_id}", response_model=AdminResponse)
async def get_admin(
    admin_id: UUID,
    current_admin: AdminUser = Depends(require_permission("view_admins")),
    db: Session = Depends(get_db)
):
    """
    Get admin by ID
    """
    admin = AdminService.get_admin_by_id(db, admin_id)
    
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Admin not found"
        )
    
    return AdminResponse.from_orm(admin)


@router.put("/{admin_id}", response_model=AdminResponse)
async def update_admin(
    admin_id: UUID,
    request: AdminUpdateRequest,
    current_admin: AdminUser = Depends(require_permission("manage_admins")),
    db: Session = Depends(get_db)
):
    """
    Update admin user
    """
    try:
        admin = AdminService.update_admin(db, admin_id, request)
        
        if not admin:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Admin not found"
            )
        
        return AdminResponse.from_orm(admin)
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Update admin error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while updating admin"
        )


@router.delete("/{admin_id}", response_model=MessageResponse)
async def deactivate_admin(
    admin_id: UUID,
    current_admin: AdminUser = Depends(require_permission("manage_admins")),
    db: Session = Depends(get_db)
):
    """
    Deactivate admin user
    """
    # Prevent self-deactivation
    if admin_id == current_admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate yourself"
        )
    
    try:
        success = AdminService.deactivate_admin(db, admin_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Admin not found"
            )
        
        return MessageResponse(message="Admin deactivated successfully")
        
    except Exception as e:
        logger.error(f"Deactivate admin error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while deactivating admin"
        )