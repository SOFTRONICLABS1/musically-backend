from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Optional
from uuid import UUID

from app.db.database import get_db
from app.schemas.social import (
    FollowResponse, FollowersListResponse, FollowingListResponse,
    FollowStatsResponse, LikeResponse, LikedContentListResponse,
    ContentLikeStatsResponse
)
from app.services.social_service import SocialService
from app.core.dependencies import get_current_user
from app.models.user import User
import logging

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Social"])


# Follow/Unfollow endpoints
@router.post("/users/{user_id}/follow", response_model=FollowResponse)
async def follow_user(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Follow another user"""
    try:
        follow = SocialService.follow_user(db, current_user.id, user_id)
        return FollowResponse.from_orm(follow)
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Follow user error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while following user"
        )


@router.delete("/users/{user_id}/unfollow")
async def unfollow_user(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Unfollow a user"""
    try:
        success = SocialService.unfollow_user(db, current_user.id, user_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Follow relationship not found"
            )
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"message": "Successfully unfollowed user"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unfollow user error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while unfollowing user"
        )


@router.get("/users/{user_id}/followers", response_model=FollowersListResponse)
async def get_user_followers(
    user_id: UUID,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get list of followers for a user"""
    try:
        followers, total = SocialService.get_followers(db, user_id, page, per_page)
        
        total_pages = (total + per_page - 1) // per_page
        
        return FollowersListResponse(
            followers=followers,
            total=total,
            page=page,
            per_page=per_page,
            total_pages=total_pages
        )
        
    except Exception as e:
        logger.error(f"Get followers error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while fetching followers"
        )


@router.get("/users/{user_id}/following", response_model=FollowingListResponse)
async def get_user_following(
    user_id: UUID,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get list of users that a user is following"""
    try:
        following, total = SocialService.get_following(db, user_id, page, per_page)
        
        total_pages = (total + per_page - 1) // per_page
        
        return FollowingListResponse(
            following=following,
            total=total,
            page=page,
            per_page=per_page,
            total_pages=total_pages
        )
        
    except Exception as e:
        logger.error(f"Get following error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while fetching following"
        )


@router.get("/users/{user_id}/follow-stats", response_model=FollowStatsResponse)
async def get_user_follow_stats(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get follow statistics for a user"""
    try:
        stats = SocialService.get_follow_stats(db, user_id)
        return stats
        
    except Exception as e:
        logger.error(f"Get follow stats error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while fetching follow stats"
        )


@router.get("/users/{user_id}/is-following")
async def check_if_following(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Check if current user is following another user"""
    try:
        is_following = SocialService.is_following(db, current_user.id, user_id)
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"is_following": is_following}
        )
        
    except Exception as e:
        logger.error(f"Check following error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while checking follow status"
        )


# Like/Unlike endpoints
@router.post("/content/{content_id}/like", response_model=LikeResponse)
async def like_content(
    content_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Like a content"""
    try:
        like = SocialService.like_content(db, current_user.id, content_id)
        return LikeResponse.from_orm(like)
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Like content error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while liking content"
        )


@router.delete("/content/{content_id}/unlike")
async def unlike_content(
    content_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Unlike a content"""
    try:
        success = SocialService.unlike_content(db, current_user.id, content_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Like not found"
            )
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"message": "Successfully unliked content"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unlike content error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while unliking content"
        )


@router.get("/content/{content_id}/likes", response_model=ContentLikeStatsResponse)
async def get_content_likes(
    content_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get like statistics for a content"""
    try:
        user_id = current_user.id
        stats = SocialService.get_content_likes(db, content_id, user_id)
        return stats
        
    except Exception as e:
        logger.error(f"Get content likes error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while fetching content likes"
        )


@router.get("/users/{user_id}/liked-content", response_model=LikedContentListResponse)
async def get_user_liked_content(
    user_id: UUID,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get list of content liked by a user"""
    try:
        content, total = SocialService.get_user_liked_content(db, user_id, page, per_page)
        
        total_pages = (total + per_page - 1) // per_page
        
        return LikedContentListResponse(
            content=content,
            total=total,
            page=page,
            per_page=per_page,
            total_pages=total_pages
        )
        
    except Exception as e:
        logger.error(f"Get liked content error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while fetching liked content"
        )


@router.get("/my/followers", response_model=FollowersListResponse)
async def get_my_followers(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get list of current user's followers"""
    try:
        followers, total = SocialService.get_followers(db, current_user.id, page, per_page)
        
        total_pages = (total + per_page - 1) // per_page
        
        return FollowersListResponse(
            followers=followers,
            total=total,
            page=page,
            per_page=per_page,
            total_pages=total_pages
        )
        
    except Exception as e:
        logger.error(f"Get my followers error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while fetching your followers"
        )


@router.get("/my/following", response_model=FollowingListResponse)
async def get_my_following(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get list of users current user is following"""
    try:
        following, total = SocialService.get_following(db, current_user.id, page, per_page)
        
        total_pages = (total + per_page - 1) // per_page
        
        return FollowingListResponse(
            following=following,
            total=total,
            page=page,
            per_page=per_page,
            total_pages=total_pages
        )
        
    except Exception as e:
        logger.error(f"Get my following error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while fetching your following"
        )


@router.get("/my/liked-content", response_model=LikedContentListResponse)
async def get_my_liked_content(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get list of content liked by current user"""
    try:
        content, total = SocialService.get_user_liked_content(db, current_user.id, page, per_page)
        
        total_pages = (total + per_page - 1) // per_page
        
        return LikedContentListResponse(
            content=content,
            total=total,
            page=page,
            per_page=per_page,
            total_pages=total_pages
        )
        
    except Exception as e:
        logger.error(f"Get my liked content error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while fetching your liked content"
        )