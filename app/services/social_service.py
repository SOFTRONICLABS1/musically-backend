from sqlalchemy.orm import Session
from sqlalchemy import and_, func, desc
from typing import List, Optional, Tuple
from uuid import UUID
import logging

from app.models.user import User, Follow, Content, ContentLike
from app.schemas.social import (
    UserFollowInfo, FollowStatsResponse,
    ContentLikeInfo, ContentLikeStatsResponse
)

logger = logging.getLogger(__name__)


class SocialService:
    
    @staticmethod
    def follow_user(db: Session, follower_id: UUID, following_id: UUID) -> Optional[Follow]:
        """Follow a user"""
        
        # Check if user is trying to follow themselves
        if follower_id == following_id:
            raise ValueError("Cannot follow yourself")
        
        # Check if following user exists
        following_user = db.query(User).filter(User.id == following_id).first()
        if not following_user:
            raise ValueError("User to follow not found")
        
        # Check if already following
        existing = db.query(Follow).filter(
            and_(
                Follow.follower_id == follower_id,
                Follow.following_id == following_id
            )
        ).first()
        
        if existing:
            raise ValueError("Already following this user")
        
        # Create follow relationship
        follow = Follow(
            follower_id=follower_id,
            following_id=following_id
        )
        
        db.add(follow)
        db.commit()
        db.refresh(follow)
        
        return follow
    
    @staticmethod
    def unfollow_user(db: Session, follower_id: UUID, following_id: UUID) -> bool:
        """Unfollow a user"""
        
        follow = db.query(Follow).filter(
            and_(
                Follow.follower_id == follower_id,
                Follow.following_id == following_id
            )
        ).first()
        
        if not follow:
            return False
        
        db.delete(follow)
        db.commit()
        
        return True
    
    @staticmethod
    def get_followers(
        db: Session, 
        user_id: UUID,
        page: int = 1,
        per_page: int = 20
    ) -> Tuple[List[UserFollowInfo], int]:
        """Get list of followers for a user"""
        
        query = db.query(
            User.id,
            User.username,
            User.signup_username,
            User.profile_image_url,
            User.bio,
            User.is_verified,
            Follow.created_at.label('followed_at')
        ).join(
            Follow, Follow.follower_id == User.id
        ).filter(
            Follow.following_id == user_id
        )
        
        # Get total count
        total = query.count()
        
        # Apply pagination
        query = query.order_by(desc(Follow.created_at))
        query = query.offset((page - 1) * per_page)
        query = query.limit(per_page)
        
        followers = []
        for row in query.all():
            followers.append(UserFollowInfo(
                id=row.id,
                username=row.username,
                signup_username=row.signup_username,
                profile_image_url=row.profile_image_url,
                bio=row.bio,
                is_verified=row.is_verified,
                followed_at=row.followed_at
            ))
        
        return followers, total
    
    @staticmethod
    def get_following(
        db: Session,
        user_id: UUID,
        page: int = 1,
        per_page: int = 20
    ) -> Tuple[List[UserFollowInfo], int]:
        """Get list of users that a user is following"""
        
        query = db.query(
            User.id,
            User.username,
            User.signup_username,
            User.profile_image_url,
            User.bio,
            User.is_verified,
            Follow.created_at.label('followed_at')
        ).join(
            Follow, Follow.following_id == User.id
        ).filter(
            Follow.follower_id == user_id
        )
        
        # Get total count
        total = query.count()
        
        # Apply pagination
        query = query.order_by(desc(Follow.created_at))
        query = query.offset((page - 1) * per_page)
        query = query.limit(per_page)
        
        following = []
        for row in query.all():
            following.append(UserFollowInfo(
                id=row.id,
                username=row.username,
                signup_username=row.signup_username,
                profile_image_url=row.profile_image_url,
                bio=row.bio,
                is_verified=row.is_verified,
                followed_at=row.followed_at
            ))
        
        return following, total
    
    @staticmethod
    def get_follow_stats(db: Session, user_id: UUID) -> FollowStatsResponse:
        """Get follow statistics for a user"""
        
        followers_count = db.query(Follow).filter(
            Follow.following_id == user_id
        ).count()
        
        following_count = db.query(Follow).filter(
            Follow.follower_id == user_id
        ).count()
        
        return FollowStatsResponse(
            followers_count=followers_count,
            following_count=following_count
        )
    
    @staticmethod
    def is_following(db: Session, follower_id: UUID, following_id: UUID) -> bool:
        """Check if one user is following another"""
        
        follow = db.query(Follow).filter(
            and_(
                Follow.follower_id == follower_id,
                Follow.following_id == following_id
            )
        ).first()
        
        return follow is not None
    
    @staticmethod
    def like_content(db: Session, user_id: UUID, content_id: UUID) -> Optional[ContentLike]:
        """Like a content"""
        
        # Check if content exists and is accessible
        content = db.query(Content).filter(Content.id == content_id).first()
        if not content:
            raise ValueError("Content not found")
        
        # Check if already liked
        existing = db.query(ContentLike).filter(
            and_(
                ContentLike.user_id == user_id,
                ContentLike.content_id == content_id
            )
        ).first()
        
        if existing:
            raise ValueError("Content already liked")
        
        # Create like
        like = ContentLike(
            user_id=user_id,
            content_id=content_id
        )
        
        db.add(like)
        db.commit()
        db.refresh(like)
        
        return like
    
    @staticmethod
    def unlike_content(db: Session, user_id: UUID, content_id: UUID) -> bool:
        """Unlike a content"""
        
        like = db.query(ContentLike).filter(
            and_(
                ContentLike.user_id == user_id,
                ContentLike.content_id == content_id
            )
        ).first()
        
        if not like:
            return False
        
        db.delete(like)
        db.commit()
        
        return True
    
    @staticmethod
    def get_content_likes(
        db: Session,
        content_id: UUID,
        current_user_id: Optional[UUID] = None
    ) -> ContentLikeStatsResponse:
        """Get like statistics for a content"""
        
        likes_count = db.query(ContentLike).filter(
            ContentLike.content_id == content_id
        ).count()
        
        is_liked = False
        if current_user_id:
            like = db.query(ContentLike).filter(
                and_(
                    ContentLike.user_id == current_user_id,
                    ContentLike.content_id == content_id
                )
            ).first()
            is_liked = like is not None
        
        return ContentLikeStatsResponse(
            likes_count=likes_count,
            is_liked=is_liked
        )
    
    @staticmethod
    def get_user_liked_content(
        db: Session,
        user_id: UUID,
        page: int = 1,
        per_page: int = 20
    ) -> Tuple[List[ContentLikeInfo], int]:
        """Get list of content liked by a user"""
        
        query = db.query(
            Content.id,
            Content.title,
            Content.description,
            Content.content_type,
            Content.media_type,
            Content.user_id,
            User.username,
            ContentLike.created_at.label('liked_at')
        ).join(
            ContentLike, ContentLike.content_id == Content.id
        ).join(
            User, User.id == Content.user_id
        ).filter(
            ContentLike.user_id == user_id
        )
        
        # Get total count
        total = query.count()
        
        # Apply pagination
        query = query.order_by(desc(ContentLike.created_at))
        query = query.offset((page - 1) * per_page)
        query = query.limit(per_page)
        
        liked_content = []
        for row in query.all():
            liked_content.append(ContentLikeInfo(
                id=row.id,
                title=row.title,
                description=row.description,
                content_type=row.content_type,
                media_type=row.media_type,
                user_id=row.user_id,
                username=row.username,
                liked_at=row.liked_at
            ))
        
        return liked_content, total
    
    @staticmethod
    def get_content_likers(
        db: Session,
        content_id: UUID,
        page: int = 1,
        per_page: int = 20
    ) -> Tuple[List[UserFollowInfo], int]:
        """Get list of users who liked a content"""
        
        query = db.query(
            User.id,
            User.username,
            User.signup_username,
            User.profile_image_url,
            User.bio,
            User.is_verified,
            ContentLike.created_at.label('followed_at')
        ).join(
            ContentLike, ContentLike.user_id == User.id
        ).filter(
            ContentLike.content_id == content_id
        )
        
        # Get total count
        total = query.count()
        
        # Apply pagination
        query = query.order_by(desc(ContentLike.created_at))
        query = query.offset((page - 1) * per_page)
        query = query.limit(per_page)
        
        likers = []
        for row in query.all():
            likers.append(UserFollowInfo(
                id=row.id,
                username=row.username,
                signup_username=row.signup_username,
                profile_image_url=row.profile_image_url,
                bio=row.bio,
                is_verified=row.is_verified,
                followed_at=row.followed_at  # Actually liked_at but reusing schema
            ))
        
        return likers, total