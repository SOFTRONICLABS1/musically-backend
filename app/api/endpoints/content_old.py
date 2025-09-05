from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Query, Form
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
import os
import shutil
from pathlib import Path
import mimetypes
import uuid as uuid_lib

from app.db.database import get_db
from app.schemas.content import (
    ContentCreate, ContentUpdate, ContentResponse, ContentListResponse,
    ContentFilters, FileUploadResponse, SocialLinkValidationResponse,
    ContentType, MediaType, SocialPlatform, AccessType
)
from app.services.content_service import ContentService
from app.core.dependencies import get_current_user
from app.models.user import User
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/content", tags=["Content"])

# Configuration
UPLOAD_DIR = "uploads/content"
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
ALLOWED_AUDIO_TYPES = {"audio/mpeg", "audio/wav", "audio/ogg", "audio/m4a", "audio/aac"}
ALLOWED_VIDEO_TYPES = {"video/mp4", "video/avi", "video/mov", "video/wmv", "video/webm"}


@router.post("/", response_model=ContentResponse)
async def create_content(
    content_data: ContentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create new content (social link or notes-only)
    For media files, use the upload endpoint first, then create content
    """
    try:
        # Validate social links if provided
        if content_data.content_type == ContentType.SOCIAL_LINK and content_data.social_url:
            validation = ContentService.validate_social_link(str(content_data.social_url))
            if not validation.is_valid:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid social media link: {validation.error_message}"
                )
        
        content = ContentService.create_content(db, current_user.id, content_data)
        
        return ContentResponse.from_orm(content)
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Content creation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while creating content"
        )


@router.post("/upload-media", response_model=FileUploadResponse)
async def upload_media_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    """
    Upload a media file (audio/video) and return the file URL
    Use this before creating content with media_file type
    """
    try:
        # Validate file size
        if file.size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File too large. Maximum size is {MAX_FILE_SIZE // (1024*1024)}MB"
            )
        
        # Validate file type
        content_type = file.content_type
        if content_type not in {*ALLOWED_AUDIO_TYPES, *ALLOWED_VIDEO_TYPES}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported file type. Supported formats: MP3, WAV, OGG, M4A, AAC, MP4, AVI, MOV, WMV, WEBM"
            )
        
        # Create upload directory if it doesn't exist
        upload_path = Path(UPLOAD_DIR)
        upload_path.mkdir(parents=True, exist_ok=True)
        
        # Generate unique filename
        file_extension = Path(file.filename).suffix
        unique_filename = f"{uuid_lib.uuid4()}{file_extension}"
        file_path = upload_path / unique_filename
        
        # Save file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Construct URL (in production, this might be a CDN URL)
        file_url = f"/uploads/content/{unique_filename}"
        
        return FileUploadResponse(
            url=file_url,
            file_name=unique_filename,
            file_size=file.size,
            content_type=content_type
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"File upload error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while uploading the file"
        )


@router.post("/create-with-media", response_model=ContentResponse)
async def create_content_with_media(
    title: str = Form(...),
    content_type: ContentType = Form(...),
    media_type: MediaType = Form(...),
    description: Optional[str] = Form(None),
    tempo: Optional[int] = Form(None),
    is_public: bool = Form(True),
    access_type: AccessType = Form(AccessType.FREE),
    tags: Optional[str] = Form(None),  # Comma-separated tags
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create content with media file in a single request
    """
    try:
        # First upload the file
        if file.size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File too large. Maximum size is {MAX_FILE_SIZE // (1024*1024)}MB"
            )
        
        content_type_mime = file.content_type
        if content_type_mime not in {*ALLOWED_AUDIO_TYPES, *ALLOWED_VIDEO_TYPES}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported file type"
            )
        
        # Create upload directory and save file
        upload_path = Path(UPLOAD_DIR)
        upload_path.mkdir(parents=True, exist_ok=True)
        
        file_extension = Path(file.filename).suffix
        unique_filename = f"{uuid_lib.uuid4()}{file_extension}"
        file_path = upload_path / unique_filename
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        file_url = f"/uploads/content/{unique_filename}"
        
        # Parse tags if provided
        tags_list = None
        if tags:
            tags_list = [tag.strip() for tag in tags.split(",") if tag.strip()]
        
        # Create content data
        content_data = ContentCreate(
            title=title,
            description=description,
            content_type=content_type,
            media_type=media_type,
            tempo=tempo,
            is_public=is_public,
            access_type=access_type,
            tags=tags_list
        )
        
        # Create content
        content = ContentService.create_content(db, current_user.id, content_data)
        
        # Update with media URL
        content = ContentService.update_media_url(db, content.id, current_user.id, file_url)
        
        return ContentResponse.from_orm(content)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Content with media creation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while creating content with media"
        )


@router.get("/my-content", response_model=ContentListResponse)
async def get_my_content(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    content_type: Optional[ContentType] = Query(None),
    media_type: Optional[MediaType] = Query(None),
    social_platform: Optional[SocialPlatform] = Query(None),
    access_type: Optional[AccessType] = Query(None),
    is_public: Optional[bool] = Query(None),
    search: Optional[str] = Query(None, max_length=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current user's content with filtering and pagination
    """
    try:
        filters = ContentFilters(
            page=page,
            per_page=per_page,
            content_type=content_type,
            media_type=media_type,
            social_platform=social_platform,
            access_type=access_type,
            is_public=is_public,
            search=search
        )
        
        contents, total = ContentService.get_user_content(db, current_user.id, filters)
        
        total_pages = (total + per_page - 1) // per_page
        
        return ContentListResponse(
            contents=[ContentResponse.from_orm(content) for content in contents],
            total=total,
            page=page,
            per_page=per_page,
            total_pages=total_pages
        )
        
    except Exception as e:
        logger.error(f"Get user content error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while fetching content"
        )


@router.get("/public", response_model=ContentListResponse)
async def get_public_content(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    content_type: Optional[ContentType] = Query(None),
    media_type: Optional[MediaType] = Query(None),
    social_platform: Optional[SocialPlatform] = Query(None),
    search: Optional[str] = Query(None, max_length=100),
    db: Session = Depends(get_db)
):
    """
    Get public content with filtering and pagination
    """
    try:
        filters = ContentFilters(
            page=page,
            per_page=per_page,
            content_type=content_type,
            media_type=media_type,
            social_platform=social_platform,
            access_type=AccessType.FREE,
            is_public=True,
            search=search
        )
        
        contents, total = ContentService.get_public_content(db, filters)
        
        total_pages = (total + per_page - 1) // per_page
        
        return ContentListResponse(
            contents=[ContentResponse.from_orm(content) for content in contents],
            total=total,
            page=page,
            per_page=per_page,
            total_pages=total_pages
        )
        
    except Exception as e:
        logger.error(f"Get public content error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while fetching public content"
        )


@router.get("/{content_id}", response_model=ContentResponse)
async def get_content(
    content_id: UUID,
    current_user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get content by ID
    """
    try:
        user_id = current_user.id if current_user else None
        content = ContentService.get_content_by_id(db, content_id, user_id)
        
        if not content:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Content not found or access denied"
            )
        
        return ContentResponse.from_orm(content)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get content error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while fetching content"
        )


@router.put("/{content_id}", response_model=ContentResponse)
async def update_content(
    content_id: UUID,
    update_data: ContentUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update content owned by current user
    """
    try:
        # Validate social links if being updated
        if update_data.social_url:
            validation = ContentService.validate_social_link(str(update_data.social_url))
            if not validation.is_valid:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid social media link: {validation.error_message}"
                )
        
        content = ContentService.update_content(db, content_id, current_user.id, update_data)
        
        if not content:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Content not found or access denied"
            )
        
        return ContentResponse.from_orm(content)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update content error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while updating content"
        )


@router.delete("/{content_id}")
async def delete_content(
    content_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete content owned by current user
    """
    try:
        success = ContentService.delete_content(db, content_id, current_user.id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Content not found or access denied"
            )
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"message": "Content deleted successfully"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete content error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while deleting content"
        )


@router.post("/{content_id}/play")
async def increment_play_count(
    content_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Increment play count for content (public endpoint)
    """
    try:
        success = ContentService.increment_play_count(db, content_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Content not found"
            )
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"message": "Play count incremented"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Increment play count error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while updating play count"
        )


@router.post("/validate-social-link", response_model=SocialLinkValidationResponse)
async def validate_social_link(
    url: str = Query(..., description="Social media URL to validate")
):
    """
    Validate a social media link and extract metadata
    """
    try:
        validation = ContentService.validate_social_link(url)
        return validation
        
    except Exception as e:
        logger.error(f"Social link validation error: {e}")
        return SocialLinkValidationResponse(
            is_valid=False,
            error_message=f"Validation error: {str(e)}"
        )