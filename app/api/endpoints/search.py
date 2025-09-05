from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.db.database import get_db
from app.schemas.search import SearchRequest, UnifiedSearchResponse
from app.schemas.auth import UserResponse
from app.schemas.content import ContentResponse
from app.schemas.game import GameResponse
from app.services.search_service import SearchService
from app.services.content_service import ContentService
from app.core.dependencies import get_current_user
from app.models.user import User
import logging

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Search"])


@router.get("/", response_model=UnifiedSearchResponse)
async def unified_search(
    q: str = Query(..., min_length=1, max_length=100, description="Search query"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    include_users: bool = Query(True, description="Include users in search results"),
    include_content: bool = Query(True, description="Include content in search results"),
    include_games: bool = Query(True, description="Include games in search results"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Unified search across users, content, and games.
    
    **Search fields by entity type:**
    
    **Users:**
    - username
    - signup_username (OAuth provider name)
    - email
    - bio
    - instruments_taught
    - teaching_style
    - location
    
    **Content:**
    - title
    - description
    - tags
    
    **Games:**
    - title
    - description
    
    Returns paginated results for each entity type.
    """
    try:
        search_request = SearchRequest(
            query=q,
            page=page,
            per_page=per_page,
            include_users=include_users,
            include_content=include_content,
            include_games=include_games
        )
        
        results = SearchService.unified_search(db, search_request)
        
        return UnifiedSearchResponse(
            query=results['query'],
            users=[UserResponse.from_orm(user) for user in results['users']],
            content=[ContentResponse(**ContentService.content_to_response(content)) for content in results['content']],
            games=[GameResponse.from_orm(game) for game in results['games']],
            total_users=results['total_users'],
            total_content=results['total_content'],
            total_games=results['total_games'],
            page=results['page'],
            per_page=results['per_page']
        )
        
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while performing search"
        )