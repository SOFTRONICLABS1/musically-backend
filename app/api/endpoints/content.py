from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID

from app.db.database import get_db
from app.schemas.content import (
    ContentCreate, ContentUpdate, ContentResponse, ContentListResponse,
    ContentFilters, MediaUploadRequest, S3PresignedUploadResponse, S3PresignedDownloadResponse,
    SocialLinkValidationResponse, ContentType, MediaType, SocialPlatform, AccessType
)
from app.services.content_service import ContentService
from app.services.game_service import GameService
from app.schemas.game import ContentWithGamesResponse, GameResponse
from app.core.dependencies import get_current_user
from app.models.user import User
import logging

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Content"])


@router.post("/", response_model=ContentResponse)
async def create_content(
    content_data: ContentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create new content (social link or notes-only)
    For media files, use the upload flow: get-upload-url -> upload to S3 -> create content
    """
    try:
        # Validate that media files don't try to create content without S3 URL
        if content_data.content_type == ContentType.MEDIA_FILE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="For media files, use the upload flow: /get-upload-url -> upload to S3 -> /create-with-s3-key"
            )
        
        # Validate social links if provided
        if content_data.content_type == ContentType.SOCIAL_LINK and content_data.social_url:
            validation = ContentService.validate_social_link(str(content_data.social_url))
            if not validation.is_valid:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid social media link: {validation.error_message}"
                )
        
        content = ContentService.create_content(db, current_user.id, content_data)
        
        # Associate content with games if game_ids provided
        if content_data.game_ids:
            for game_id in content_data.game_ids:
                GameService.add_content_to_game(db, content.id, game_id, current_user.id)
        
        # Convert to response with download URL
        response_data = ContentService.content_to_response(content)
        return ContentResponse(**response_data)
        
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


@router.post("/get-upload-url", response_model=S3PresignedUploadResponse)
async def get_upload_url(
    upload_request: MediaUploadRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Generate pre-signed URL for uploading media files directly to S3
    Step 1 of the upload flow
    """
    try:
        upload_response = ContentService.generate_upload_presigned_url(
            user_id=current_user.id,
            upload_request=upload_request
        )
        
        return upload_response
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Upload URL generation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while generating upload URL"
        )


@router.post("/create-with-s3-key", response_model=ContentResponse)
async def create_content_with_s3_key(
    content_data: ContentCreate,
    s3_key: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create content with uploaded S3 file
    Step 2 of the upload flow (after uploading to S3)
    """
    try:
        # Ensure this is for media file content
        if content_data.content_type != ContentType.MEDIA_FILE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This endpoint is only for media file content"
            )
        
        # Create content first
        content = ContentService.create_content(db, current_user.id, content_data)
        
        # Update with S3 key
        content = ContentService.update_media_url(db, content.id, current_user.id, s3_key)
        
        if not content:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update content with media URL"
            )
        
        # Associate content with games if game_ids provided
        if content_data.game_ids:
            for game_id in content_data.game_ids:
                GameService.add_content_to_game(db, content.id, game_id, current_user.id)
        
        # Convert to response with download URL
        response_data = ContentService.content_to_response(content)
        return ContentResponse(**response_data)
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Content with S3 creation error: {e}")
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
            contents=[ContentResponse(**ContentService.content_to_response(content)) for content in contents],
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
    current_user: User = Depends(get_current_user),
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
            contents=[ContentResponse(**ContentService.content_to_response(content)) for content in contents],
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get content by ID
    """
    try:
        user_id = current_user.id
        content = ContentService.get_content_by_id(db, content_id, user_id)
        
        if not content:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Content not found or access denied"
            )
        
        # Convert to response with download URL
        response_data = ContentService.content_to_response(content)
        return ContentResponse(**response_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get content error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while fetching content"
        )


@router.get("/{content_id}/download", response_model=S3PresignedDownloadResponse)
async def get_download_url(
    content_id: UUID,
    attachment: bool = Query(False, description="Force download as attachment"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get pre-signed download URL for media content
    Provides controlled access to S3 files
    """
    try:
        user_id = current_user.id
        
        download_response = ContentService.generate_download_presigned_url(
            db=db,
            content_id=content_id,
            user_id=user_id,
            attachment=attachment
        )
        
        if not download_response:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Content not found, no media file, or access denied"
            )
        
        return download_response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Download URL generation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while generating download URL"
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
        
        # Convert to response with download URL
        response_data = ContentService.content_to_response(content)
        return ContentResponse(**response_data)
        
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
    Also deletes associated S3 files
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



@router.get("/user/{owner_user_id}", response_model=ContentListResponse)
async def get_user_content(
    owner_user_id: UUID,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    content_type: Optional[ContentType] = Query(None),
    media_type: Optional[MediaType] = Query(None),
    social_platform: Optional[SocialPlatform] = Query(None),
    search: Optional[str] = Query(None, max_length=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get user's content based on subscription status.
    Returns all content (public + private) if subscribed, only public content otherwise.
    """
    try:
        filters = ContentFilters(
            page=page,
            per_page=per_page,
            content_type=content_type,
            media_type=media_type,
            social_platform=social_platform,
            search=search
        )
        
        contents, total = ContentService.get_user_content_by_subscription(
            db=db,
            owner_user_id=owner_user_id,
            viewer_user_id=current_user.id,
            filters=filters
        )
        
        total_pages = (total + per_page - 1) // per_page
        
        return ContentListResponse(
            contents=[ContentResponse(**ContentService.content_to_response(content)) for content in contents],
            total=total,
            page=page,
            per_page=per_page,
            total_pages=total_pages
        )
        
    except Exception as e:
        logger.error(f"Get user content error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while fetching user content"
        )


@router.get("/{content_id}/games", response_model=ContentWithGamesResponse)
async def get_content_games(
    content_id: UUID,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all games associated with content"""
    try:
        # Verify content exists and user has access
        user_id = current_user.id
        content = ContentService.get_content_by_id(db, content_id, user_id)
        
        if not content:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Content not found or access denied"
            )
        
        games, total = GameService.get_content_games(db, content_id, page, per_page)
        
        total_pages = (total + per_page - 1) // per_page
        
        return ContentWithGamesResponse(
            content_id=content_id,
            games=[GameResponse.from_orm(game) for game in games],
            total=total,
            page=page,
            per_page=per_page,
            total_pages=total_pages
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get content games error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while fetching content games"
        )