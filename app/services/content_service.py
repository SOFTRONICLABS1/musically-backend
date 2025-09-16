from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, asc, func
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID
import re
import requests
from urllib.parse import urlparse, parse_qs

from app.models.user import Content, User
from app.schemas.content import (
    ContentCreate, ContentUpdate, ContentFilters,
    ContentType, SocialPlatform, SocialLinkValidationResponse,
    MediaUploadRequest, S3PresignedUploadResponse, S3PresignedDownloadResponse
)
from app.services.s3_service import s3_service
from app.services.lambda_client import lambda_client
from app.services.hybrid_cache_service import hybrid_cache
from app.services.redis_service import CacheKeys
# Keep Redis as fallback import
try:
    from app.services.redis_service import redis_service
except ImportError:
    redis_service = None
import logging
import re
import hashlib

logger = logging.getLogger(__name__)


class ContentService:
    
    @staticmethod
    def _auto_generate_tags(content_data: ContentCreate) -> List[str]:
        """Auto-generate tags based on content data"""
        tags = []
        
        # Add content type tags
        if content_data.content_type == ContentType.MEDIA_FILE:
            if content_data.media_type:
                tags.append(content_data.media_type.value)
        elif content_data.content_type == ContentType.SOCIAL_LINK:
            tags.append("social")
            if content_data.social_platform:
                tags.append(content_data.social_platform.value)
        elif content_data.content_type == ContentType.NOTES_ONLY:
            tags.append("music-notation")
        
        # Extract tags from title and description
        text_content = f"{content_data.title} {content_data.description or ''}"
        
        # Music-related keywords
        music_keywords = {
            'jazz': 'jazz', 'rock': 'rock', 'pop': 'pop', 'classical': 'classical',
            'blues': 'blues', 'country': 'country', 'electronic': 'electronic',
            'hip-hop': 'hip-hop', 'rap': 'rap', 'folk': 'folk', 'reggae': 'reggae',
            'guitar': 'guitar', 'piano': 'piano', 'drums': 'drums', 'violin': 'violin',
            'saxophone': 'saxophone', 'trumpet': 'trumpet', 'bass': 'bass',
            'improvisation': 'improvisation', 'scales': 'scales', 'chords': 'chords',
            'lesson': 'lesson', 'tutorial': 'tutorial', 'practice': 'practice'
        }
        
        text_lower = text_content.lower()
        for keyword, tag in music_keywords.items():
            if keyword in text_lower and tag not in tags:
                tags.append(tag)
        
        # Add tempo-based tags
        if content_data.tempo:
            if content_data.tempo < 80:
                tags.append("slow")
            elif content_data.tempo > 140:
                tags.append("fast")
            else:
                tags.append("moderate")
        
        return tags[:10]  # Max 10 tags
    
    @staticmethod
    def create_content(db: Session, user_id: UUID, content_data: ContentCreate) -> Content:
        """Create a new content entry with automatic music extraction for social links"""
        
        # Extract music data from social links if not provided
        notes_data = content_data.notes_data
        tempo = content_data.tempo
        extracted_metadata = None
        
        if content_data.content_type == ContentType.SOCIAL_LINK and content_data.social_url:
            # Only extract if notes_data not already provided
            if not notes_data:
                try:
                    logger.info(f"Extracting music data from social link: {content_data.social_url}")
                    
                    # Call the firebase-auth Lambda for music extraction
                    extraction_result = lambda_client.invoke_music_extraction(str(content_data.social_url))
                    
                    if extraction_result:
                        metadata = extraction_result.get('metadata')
                        extracted_notes = extraction_result.get('notes_data')
                        
                        if extracted_notes:
                            notes_data = extracted_notes
                            logger.info(f"Successfully extracted notes data for: {content_data.title}")
                        
                        # Update tempo if extracted
                        if metadata and metadata.get('tempo'):
                            tempo = metadata.get('tempo')
                        
                        extracted_metadata = metadata
                    else:
                        logger.warning(f"Music extraction Lambda returned no data for: {content_data.social_url}")
                    
                except Exception as e:
                    logger.warning(f"Failed to extract music data from {content_data.social_url}: {e}")
                    # Continue without extraction
        
        # Auto-generate tags if not provided
        tags = content_data.tags
        if not tags or len(tags) == 0:
            tags = ContentService._auto_generate_tags(content_data)
            
            # Add tags from extracted metadata
            if extracted_metadata and extracted_metadata.get('tags'):
                music_tags = [tag.lower() for tag in extracted_metadata['tags'][:5]]
                tags.extend(music_tags)
                tags = list(set(tags))[:10]  # Remove duplicates and limit to 10
            
            logger.info(f"Auto-generated tags for '{content_data.title}': {tags}")
        
        # Update description with extracted metadata if not provided
        description = content_data.description
        if not description and extracted_metadata:
            channel = extracted_metadata.get('channel', '')
            if channel:
                description = f"Content from {channel}"
                if extracted_metadata.get('duration'):
                    duration_seconds = extracted_metadata.get('duration')
                    minutes = duration_seconds // 60
                    seconds = duration_seconds % 60
                    description += f" | Duration: {minutes}:{seconds:02d}"
        
        # Create content instance
        db_content = Content(
            user_id=user_id,
            title=content_data.title,
            description=description,
            content_type=content_data.content_type.value,
            media_type=content_data.media_type.value if content_data.media_type else None,
            social_url=str(content_data.social_url) if content_data.social_url else None,
            social_platform=content_data.social_platform.value if content_data.social_platform else None,
            notes_data=notes_data,
            tempo=tempo,
            is_public=content_data.is_public,
            access_type=content_data.access_type.value,
            tags=tags
        )
        
        db.add(db_content)
        db.commit()
        db.refresh(db_content)
        
        # Update user's total content count
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            user.total_content_created += 1
            db.commit()
        
        # Invalidate related caches
        # Invalidate user content lists
        hybrid_cache.delete_pattern(f"content:list:user:{user_id}:*")
        # Invalidate public content lists if content is public
        if db_content.is_public:
            hybrid_cache.delete_pattern("content:list:public:*")
        logger.debug(f"Invalidated cache patterns for new content {db_content.id}")
        
        return db_content
    
    @staticmethod
    def get_content_by_id(db: Session, content_id: UUID, user_id: Optional[UUID] = None) -> Optional[Content]:
        """Get content by ID with optional user access control and caching"""
        
        # Try to get from cache first
        user_id_str = str(user_id) if user_id else "public"
        cache_key = CacheKeys.format_key(
            CacheKeys.CONTENT_BY_ID, 
            content_id=str(content_id), 
            user_id=user_id_str
        )
        
        cached_content = hybrid_cache.get(cache_key)
        if cached_content:
            logger.debug(f"Cache HIT for content {content_id}")
            # Convert dict back to Content object
            content = Content(**cached_content)
            return content
        
        logger.debug(f"Cache MISS for content {content_id}")
        
        query = db.query(Content).filter(Content.id == content_id)
        
        # If user_id is provided, check access permissions
        if user_id:
            query = query.filter(
                or_(
                    Content.user_id == user_id,  # User owns the content
                    and_(
                        Content.is_public == True,
                        Content.access_type.in_(['free', 'subscribers_only'])
                    )
                )
            )
        else:
            # Public access only
            query = query.filter(
                and_(
                    Content.is_public == True,
                    Content.access_type == 'free'
                )
            )
        
        content = query.first()
        
        # Cache the result if found
        if content:
            # Convert SQLAlchemy object to dict for caching
            content_dict = {
                'id': content.id,
                'user_id': content.user_id,
                'title': content.title,
                'description': content.description,
                'content_type': content.content_type,
                'media_type': content.media_type,
                'social_platform': content.social_platform,
                'social_url': content.social_url,
                'media_url': content.media_url,  # Use media_url instead of s3_key
                'notes_data': content.notes_data,
                'tempo': content.tempo,
                'tags': content.tags,
                'is_public': content.is_public,
                'access_type': content.access_type,
                'play_count': content.play_count,
                'created_at': content.created_at,
                'updated_at': content.updated_at
            }
            hybrid_cache.set(cache_key, content_dict, 300)  # 5 min cache
        
        return content
    
    @staticmethod
    def get_user_content(
        db: Session, 
        user_id: UUID,
        filters: ContentFilters
    ) -> Tuple[List[Content], int]:
        """Get user's content with filtering and pagination"""
        
        query = db.query(Content).filter(Content.user_id == user_id)
        
        # Apply filters
        query = ContentService._apply_filters(query, filters)
        
        # Get total count before pagination
        total = query.count()
        
        # Apply pagination and ordering
        query = query.order_by(desc(Content.created_at))
        query = query.offset((filters.page - 1) * filters.per_page)
        query = query.limit(filters.per_page)
        
        return query.all(), total
    
    @staticmethod
    def get_public_content(
        db: Session,
        filters: ContentFilters
    ) -> Tuple[List[Content], int]:
        """Get public content with filtering and pagination (cached)"""
        
        # Create cache key from filters
        filters_hash = CacheKeys.hash_filters({
            'content_type': filters.content_type.value if filters.content_type else None,
            'media_type': filters.media_type.value if filters.media_type else None,
            'social_platform': filters.social_platform.value if filters.social_platform else None,
            'search': filters.search,
            'per_page': filters.per_page
        })
        
        cache_key = CacheKeys.format_key(
            CacheKeys.CONTENT_LIST_PUBLIC, 
            page=filters.page, 
            filters_hash=filters_hash
        )
        
        # Try cache first
        cached_result = hybrid_cache.get(cache_key)
        if cached_result:
            logger.debug(f"Cache HIT for public content list page {filters.page}")
            contents = [Content(**item) for item in cached_result['contents']]
            return contents, cached_result['total']
        
        logger.debug(f"Cache MISS for public content list page {filters.page}")
        
        query = db.query(Content).filter(
            and_(
                Content.is_public == True,
                Content.access_type == 'free'
            )
        )
        
        # Apply filters
        query = ContentService._apply_filters(query, filters)
        
        # Get total count before pagination
        total = query.count()
        
        # Apply pagination and consistent ordering (changed from random for caching)
        query = query.order_by(desc(Content.created_at))
        query = query.offset((filters.page - 1) * filters.per_page)
        query = query.limit(filters.per_page)
        
        contents = query.all()
        
        # Cache results
        contents_dict = []
        for content in contents:
                content_dict = {
                    'id': content.id,
                    'user_id': content.user_id,
                    'title': content.title,
                    'description': content.description,
                    'content_type': content.content_type,
                    'media_type': content.media_type,
                    'social_platform': content.social_platform,
                    'social_url': content.social_url,
                    'media_url': content.media_url,  # Use media_url instead of s3_key
                    'notes_data': content.notes_data,
                    'tempo': content.tempo,
                    'tags': content.tags,
                    'is_public': content.is_public,
                    'access_type': content.access_type,
                    'play_count': content.play_count,
                    'created_at': content.created_at,
                    'updated_at': content.updated_at
                }
                contents_dict.append(content_dict)
        
        cache_data = {'contents': contents_dict, 'total': total}
        hybrid_cache.set(cache_key, cache_data, 86400)  # 24 hour cache for public content
        
        return contents, total
    
    @staticmethod
    def update_content(
        db: Session, 
        content_id: UUID, 
        user_id: UUID, 
        update_data: ContentUpdate
    ) -> Optional[Content]:
        """Update content owned by user"""
        
        content = db.query(Content).filter(
            and_(
                Content.id == content_id,
                Content.user_id == user_id
            )
        ).first()
        
        if not content:
            return None
        
        # Update only provided fields
        update_dict = update_data.dict(exclude_unset=True)
        
        for field, value in update_dict.items():
            if field == 'social_url' and value:
                value = str(value)
            elif field in ['social_platform', 'access_type'] and value:
                value = value.value
            
            setattr(content, field, value)
        
        db.commit()
        db.refresh(content)
        
        # Invalidate related caches
        # Invalidate specific content cache
        hybrid_cache.delete_pattern(f"content:id:{content_id}:*")
        # Invalidate user content lists
        hybrid_cache.delete_pattern(f"content:list:user:{user_id}:*")
        # Invalidate public content lists if content is/was public
        hybrid_cache.delete_pattern("content:list:public:*")
        logger.debug(f"Invalidated cache patterns for updated content {content_id}")
        
        return content
    
    @staticmethod
    def delete_content(db: Session, content_id: UUID, user_id: UUID) -> bool:
        """Delete content owned by user"""
        
        try:
            content = db.query(Content).filter(
                and_(
                    Content.id == content_id,
                    Content.user_id == user_id
                )
            ).first()
            
            if not content:
                logger.warning(f"Content {content_id} not found or not owned by user {user_id}")
                return False
            
            logger.info(f"Deleting content {content_id} by user {user_id}")
            
            # Delete associated S3 file if it exists (don't let S3 errors block deletion)
            try:
                ContentService.delete_media_file(content)
                logger.info(f"S3 file deletion attempted for content {content_id}")
            except Exception as e:
                logger.warning(f"S3 file deletion failed for content {content_id}: {e}")
                # Continue with database deletion even if S3 fails
            
            # Delete related records first (even though CASCADE should handle this)
            try:
                # Delete content likes
                from app.models.user import ContentLike, ContentGame
                
                likes_deleted = db.query(ContentLike).filter(ContentLike.content_id == content_id).delete()
                logger.info(f"Deleted {likes_deleted} content likes")
                
                # Delete content-game associations
                games_deleted = db.query(ContentGame).filter(ContentGame.content_id == content_id).delete()
                logger.info(f"Deleted {games_deleted} content-game associations")
                
                # Now delete the content
                db.delete(content)
                db.commit()
                logger.info(f"Content {content_id} deleted from database")
                
            except Exception as e:
                logger.error(f"Database deletion error for content {content_id}: {e}")
                db.rollback()
                raise
            
            # Update user's total content count
            try:
                user = db.query(User).filter(User.id == user_id).first()
                if user and user.total_content_created > 0:
                    user.total_content_created -= 1
                    db.commit()
                    logger.info(f"Updated user {user_id} content count")
            except Exception as e:
                logger.warning(f"Failed to update user content count: {e}")
                # Don't fail the whole operation for this
            
            # Invalidate related caches
            # Invalidate specific content cache
            hybrid_cache.delete_pattern(f"content:id:{content_id}:*")
            # Invalidate user content lists
            hybrid_cache.delete_pattern(f"content:list:user:{user_id}:*")
            # Invalidate public content lists
            hybrid_cache.delete_pattern("content:list:public:*")
            # Invalidate download URLs
            hybrid_cache.delete_pattern(f"content:download:{content_id}:*")
            logger.debug(f"Invalidated cache patterns for deleted content {content_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error deleting content {content_id}: {e}", exc_info=True)
            db.rollback()
            raise  # Re-raise to trigger 500 error
    
    @staticmethod
    def increment_play_count(db: Session, content_id: UUID) -> bool:
        """Increment play count for content"""
        
        content = db.query(Content).filter(Content.id == content_id).first()
        if not content:
            return False
        
        content.play_count += 1
        db.commit()
        
        return True
    
    @staticmethod
    def update_media_url(db: Session, content_id: UUID, user_id: UUID, s3_key: str) -> Optional[Content]:
        """Update S3 key for content after file upload"""
        
        content = db.query(Content).filter(
            and_(
                Content.id == content_id,
                Content.user_id == user_id,
                Content.content_type == 'media_file'
            )
        ).first()
        
        if not content:
            return None
        
        # Store S3 URL format
        content.media_url = f"s3://{s3_service._bucket_name}/{s3_key}"
        db.commit()
        db.refresh(content)
        
        return content
    
    @staticmethod
    def generate_upload_presigned_url(
        user_id: UUID,
        upload_request: MediaUploadRequest
    ) -> S3PresignedUploadResponse:
        """Generate pre-signed URL for uploading media files to S3"""
        
        # Validate file type
        is_valid, media_type = s3_service.validate_file_type(upload_request.content_type)
        if not is_valid:
            raise ValueError(f"Unsupported file type: {upload_request.content_type}")
        
        # Generate pre-signed URL
        result = s3_service.generate_upload_presigned_url(
            user_id=str(user_id),
            filename=upload_request.filename,
            content_type=upload_request.content_type,
            file_size=upload_request.file_size
        )
        
        return S3PresignedUploadResponse(**result)
    
    @staticmethod
    def generate_download_presigned_url(
        db: Session,
        content_id: UUID,
        user_id: Optional[UUID] = None,
        attachment: bool = False
    ) -> Optional[S3PresignedDownloadResponse]:
        """Generate pre-signed URL for downloading media files from S3 (cached)"""
        
        try:
            # Try cache first for download URLs (short cache)
            cache_key = CacheKeys.format_key(
                CacheKeys.CONTENT_DOWNLOAD_URL, 
                content_id=str(content_id), 
                attachment=str(attachment)
            )
            
            cached_url = hybrid_cache.get(cache_key)
            if cached_url:
                logger.debug(f"Cache HIT for download URL {content_id}")
                return S3PresignedDownloadResponse(**cached_url)
            
            logger.debug(f"Cache MISS for download URL {content_id}")
            
            # Get content and verify access
            content = ContentService.get_content_by_id(db, content_id, user_id)
            if not content or not content.media_url:
                logger.warning(f"Content not found or no media_url for content_id: {content_id}")
                return None
            
            # Extract S3 key from media URL
            s3_key = s3_service.extract_s3_key_from_url(content.media_url)
            if not s3_key:
                logger.error(f"Failed to extract S3 key from media_url: {content.media_url}")
                return None
            
            logger.info(f"Checking if S3 file exists: {s3_key}")
            
            # Check if file exists in S3
            if not s3_service.check_file_exists(s3_key):
                logger.error(f"S3 file does not exist: {s3_key}")
                return None
            
            # Get file metadata
            metadata = s3_service.get_file_metadata(s3_key)
            
            # Set content disposition for download
            content_disposition = None
            if attachment:
                safe_title = "".join(c for c in content.title if c.isalnum() or c in (' ', '-', '_')).strip()
                file_extension = s3_key.split('.')[-1] if '.' in s3_key else ''
                filename = f"{safe_title}.{file_extension}" if file_extension else safe_title
                content_disposition = f'attachment; filename="{filename}"'
            
            # Generate download URL
            download_url = s3_service.generate_download_presigned_url(
                s3_key=s3_key,
                content_disposition=content_disposition
            )
            
            response = S3PresignedDownloadResponse(
                download_url=download_url,
                expires_in=300,  # Fixed expires_in value
                file_name=content.title,
                content_type=metadata.get('content_type') if metadata else None,
                file_size=metadata.get('size') if metadata else None
            )
            
            # Cache the response for shorter time (1 min since URLs expire)
            response_dict = {
                'download_url': response.download_url,
                'expires_in': response.expires_in,
                'file_name': response.file_name,
                'content_type': response.content_type,
                'file_size': response.file_size
            }
            hybrid_cache.set(cache_key, response_dict, 60)  # 1 min cache
            
            return response
        except Exception as e:
            logger.error(f"Error generating download URL for content {content_id}: {str(e)}", exc_info=True)
            raise
    
    @staticmethod
    def delete_media_file(content: Content) -> bool:
        """Delete media file from S3 when content is deleted"""
        
        if not content.media_url or not content.media_url.startswith('s3://'):
            return True  # No S3 file to delete
        
        s3_key = s3_service.extract_s3_key_from_url(content.media_url)
        if not s3_key:
            return True  # Invalid S3 URL
        
        try:
            return s3_service.delete_file(s3_key)
        except Exception as e:
            # Log error but don't fail the content deletion
            logger.error(f"Failed to delete S3 file {s3_key}: {e}")
            return False
    
    @staticmethod
    def validate_social_link(url: str) -> SocialLinkValidationResponse:
        """Validate and extract info from social media links"""
        
        try:
            parsed_url = urlparse(url)
            domain = parsed_url.netloc.lower()
            
            # Remove www. prefix
            if domain.startswith('www.'):
                domain = domain[4:]
            
            # Detect platform
            platform = None
            if 'youtube.com' in domain or 'youtu.be' in domain:
                platform = SocialPlatform.YOUTUBE
            elif 'facebook.com' in domain or 'fb.com' in domain:
                platform = SocialPlatform.FACEBOOK
            elif 'instagram.com' in domain:
                platform = SocialPlatform.INSTAGRAM
            elif 'linkedin.com' in domain:
                platform = SocialPlatform.LINKEDIN
            elif 'tiktok.com' in domain:
                platform = SocialPlatform.TIKTOK
            elif 'twitter.com' in domain or 'x.com' in domain:
                platform = SocialPlatform.TWITTER
            
            if not platform:
                return SocialLinkValidationResponse(
                    is_valid=False,
                    error_message="Unsupported social media platform"
                )
            
            # For now, return basic validation
            # In production, you might want to fetch metadata from the URL
            return SocialLinkValidationResponse(
                is_valid=True,
                platform=platform,
                title="Social Media Content",
                description="Content from " + platform.value
            )
            
        except Exception as e:
            return SocialLinkValidationResponse(
                is_valid=False,
                error_message=f"Invalid URL: {str(e)}"
            )
    
    @staticmethod
    def _apply_filters(query, filters: ContentFilters):
        """Apply filters to content query"""
        
        if filters.content_type:
            query = query.filter(Content.content_type == filters.content_type.value)
        
        if filters.media_type:
            query = query.filter(Content.media_type == filters.media_type.value)
        
        if filters.social_platform:
            query = query.filter(Content.social_platform == filters.social_platform.value)
        
        if filters.access_type:
            query = query.filter(Content.access_type == filters.access_type.value)
        
        if filters.is_public is not None:
            query = query.filter(Content.is_public == filters.is_public)
        
        if filters.tags:
            # Search for any of the provided tags
            for tag in filters.tags:
                query = query.filter(Content.tags.any(tag.lower()))
        
        if filters.search:
            search_term = f"%{filters.search.lower()}%"
            query = query.filter(
                or_(
                    Content.title.ilike(search_term),
                    Content.description.ilike(search_term)
                )
            )
        
        return query
    
    @staticmethod
    def get_user_content_by_subscription(
        db: Session,
        owner_user_id: UUID,
        viewer_user_id: UUID,
        filters: ContentFilters
    ) -> Tuple[List[Content], int]:
        """Get user's content based on subscription status"""
        
        from app.services.subscription_service import SubscriptionService
        
        # Check if viewer is subscribed to owner
        subscription = SubscriptionService.get_subscription_status(
            db=db,
            subscriber_id=viewer_user_id,
            owner_id=owner_user_id
        )
        
        is_subscribed = subscription is not None
        
        query = db.query(Content).filter(Content.user_id == owner_user_id)
        
        # Apply access control based on subscription status
        if is_subscribed:
            # Subscribed users can see all content (public and private)
            pass  # No additional filters
        else:
            # Non-subscribed users only see public content
            query = query.filter(Content.is_public == True)
        
        # Apply other filters
        query = ContentService._apply_filters(query, filters)
        
        # Get total count before pagination
        total = query.count()
        
        # Apply pagination and ordering
        query = query.order_by(desc(Content.created_at))
        query = query.offset((filters.page - 1) * filters.per_page)
        query = query.limit(filters.per_page)
        
        return query.all(), total

    @staticmethod
    def content_to_response(content: Content, include_download_url: bool = True) -> Dict:
        """Convert Content model to response dict with download URL if applicable"""
        
        response_data = {
            "id": content.id,
            "user_id": content.user_id,
            "title": content.title,
            "description": content.description,
            "content_type": content.content_type,
            "download_url": None,
            "media_type": content.media_type,
            "social_url": content.social_url,
            "social_platform": content.social_platform,
            "notes_data": content.notes_data,
            "tempo": content.tempo,
            "is_public": content.is_public,
            "access_type": content.access_type,
            "tags": content.tags,
            "play_count": content.play_count,
            "avg_score": content.avg_score,
            "created_at": content.created_at,
            "updated_at": content.updated_at
        }
        
        # Generate download URL for media files
        if include_download_url and content.media_url and content.content_type == 'media_file':
            try:
                s3_key = s3_service.extract_s3_key_from_url(content.media_url)
                if s3_key:
                    # Generate a pre-signed URL valid for 1 hour
                    response_data["download_url"] = s3_service.generate_download_presigned_url(
                        s3_key=s3_key,
                        expire_seconds=3600
                    )
            except Exception as e:
                logger.warning(f"Failed to generate download URL for content {content.id}: {e}")
                response_data["download_url"] = None
        
        return response_data