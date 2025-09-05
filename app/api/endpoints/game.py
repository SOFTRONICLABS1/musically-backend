from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID

from app.db.database import get_db
from app.schemas.game import (
    GameCreate, GameUpdate, GameResponse, GameListResponse,
    ContentGameCreate, ContentGameResponse, GameWithContentResponse,
    ContentWithGamesResponse, GameScoreCreate, GameScoreResponse
)
from app.schemas.content import ContentResponse, ContentListResponse
from app.services.game_service import GameService
from app.services.content_service import ContentService
from app.core.dependencies import get_current_user
from app.models.user import User
import logging

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Games"])


@router.post("/", response_model=GameResponse)
async def create_game(
    game_data: GameCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new game"""
    try:
        game = GameService.create_game(db, current_user.id, game_data)
        return GameResponse.from_orm(game)
        
    except Exception as e:
        logger.error(f"Game creation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while creating game"
        )


@router.get("/", response_model=GameListResponse)
async def get_games(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None, max_length=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all games with pagination and search"""
    try:
        games, total = GameService.get_all_games(db, page, per_page, search)
        
        total_pages = (total + per_page - 1) // per_page
        
        return GameListResponse(
            games=[GameResponse.from_orm(game) for game in games],
            total=total,
            page=page,
            per_page=per_page,
            total_pages=total_pages
        )
        
    except Exception as e:
        logger.error(f"Get games error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while fetching games"
        )


@router.get("/my-games", response_model=GameListResponse)
async def get_my_games(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current user's games"""
    try:
        games, total = GameService.get_user_games(db, current_user.id, page, per_page)
        
        total_pages = (total + per_page - 1) // per_page
        
        return GameListResponse(
            games=[GameResponse.from_orm(game) for game in games],
            total=total,
            page=page,
            per_page=per_page,
            total_pages=total_pages
        )
        
    except Exception as e:
        logger.error(f"Get user games error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while fetching user games"
        )


@router.get("/{game_id}", response_model=GameResponse)
async def get_game(
    game_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get game by ID"""
    try:
        game = GameService.get_game_by_id(db, game_id)
        
        if not game:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Game not found"
            )
        
        return GameResponse.from_orm(game)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get game error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while fetching game"
        )


@router.put("/{game_id}", response_model=GameResponse)
async def update_game(
    game_id: UUID,
    update_data: GameUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update game owned by current user"""
    try:
        game = GameService.update_game(db, game_id, current_user.id, update_data)
        
        if not game:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Game not found or access denied"
            )
        
        return GameResponse.from_orm(game)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update game error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while updating game"
        )


@router.delete("/{game_id}")
async def delete_game(
    game_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete game owned by current user"""
    try:
        success = GameService.delete_game(db, game_id, current_user.id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Game not found or access denied"
            )
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"message": "Game deleted successfully"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete game error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while deleting game"
        )


@router.post("/{game_id}/content", response_model=ContentGameResponse)
async def add_content_to_game(
    game_id: UUID,
    content_game_data: ContentGameCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Add content to game (user must own the content)"""
    try:
        # Verify game_id matches URL parameter
        if content_game_data.game_id != game_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Game ID in URL must match game ID in request body"
            )
        
        content_game = GameService.add_content_to_game(
            db, content_game_data.content_id, game_id, current_user.id
        )
        
        if not content_game:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Content not found, game not found, or access denied"
            )
        
        return ContentGameResponse.from_orm(content_game)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Add content to game error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while adding content to game"
        )


@router.delete("/{game_id}/content/{content_id}")
async def remove_content_from_game(
    game_id: UUID,
    content_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Remove content from game (user must own the content)"""
    try:
        success = GameService.remove_content_from_game(db, content_id, game_id, current_user.id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Content not found, game not found, or access denied"
            )
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"message": "Content removed from game successfully"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Remove content from game error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while removing content from game"
        )


@router.get("/{game_id}/content", response_model=ContentListResponse)
async def get_game_content(
    game_id: UUID,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all content associated with a game"""
    try:
        # Verify game exists
        game = GameService.get_game_by_id(db, game_id)
        if not game:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Game not found"
            )
        
        contents, total = GameService.get_game_content(db, game_id, page, per_page)
        
        total_pages = (total + per_page - 1) // per_page
        
        return ContentListResponse(
            contents=[ContentResponse(**ContentService.content_to_response(content)) for content in contents],
            total=total,
            page=page,
            per_page=per_page,
            total_pages=total_pages
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get game content error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while fetching game content"
        )


@router.post("/{game_id}/publish")
async def publish_game(
    game_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Publish a game owned by current user"""
    try:
        success = GameService.publish_game(db, game_id, current_user.id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Game not found or access denied"
            )
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"message": "Game published successfully"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Publish game error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while publishing game"
        )


@router.post("/{game_id}/unpublish")
async def unpublish_game(
    game_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Unpublish a game owned by current user"""
    try:
        success = GameService.unpublish_game(db, game_id, current_user.id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Game not found or access denied"
            )
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"message": "Game unpublished successfully"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unpublish game error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while unpublishing game"
        )


@router.post("/{game_id}/content/{content_id}/play")
async def increment_play_count(
    game_id: UUID,
    content_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Increment play count for content-game pair"""
    try:
        success = GameService.increment_content_game_play_count(db, content_id, game_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Content-game combination not found"
            )
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"message": "Play count incremented successfully"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Increment play count error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while incrementing play count"
        )


@router.post("/scores", response_model=GameScoreResponse)
async def record_game_score(
    score_data: GameScoreCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Record a game score for current user"""
    try:
        score = GameService.record_score(db, current_user.id, score_data)
        
        if not score:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Game or content not found"
            )
        
        return GameScoreResponse.from_orm(score)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Record game score error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while recording game score"
        )