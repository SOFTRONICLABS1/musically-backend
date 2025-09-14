from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID

from app.db.database import get_db
from app.schemas.game import (
    GameCreate, GameUpdate, GameResponse, GameListResponse,
    ContentGameCreate, ContentGameResponse, GameWithContentResponse,
    ContentWithGamesResponse, GameScoreCreate, GameScoreResponse, GameScoreListResponse,
    LatestGamePlayedResponse, LatestGamesPlayedListResponse,
    GameScoreLogCreate, GameScoreLogResponse, GameScoreLogListResponse
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


@router.get("/latest-played", response_model=LatestGamesPlayedListResponse)
async def get_latest_games_played(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get latest unique games played by the current user (most recent play per game)"""
    try:
        games_data, total = GameService.get_latest_games_played(
            db, current_user.id, page, per_page
        )
        
        total_pages = (total + per_page - 1) // per_page
        
        # Convert dict data to Pydantic models
        games = [LatestGamePlayedResponse(**game_data) for game_data in games_data]
        
        return LatestGamesPlayedListResponse(
            games=games,
            total=total,
            page=page,
            per_page=per_page,
            total_pages=total_pages
        )
        
    except Exception as e:
        logger.error(f"Get latest games played error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while fetching latest games played"
        )


# NEW GAME SCORE LOGS ENDPOINTS (Append-only approach)

@router.post("/score-logs", response_model=GameScoreLogResponse)
async def create_score_log(
    score_log_data: GameScoreLogCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new game score log entry (append-only approach)"""
    try:
        score_log = GameService.create_score_log(db, current_user.id, score_log_data)
        
        if not score_log:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Game or content not found"
            )
        
        return GameScoreLogResponse.from_orm(score_log)
        
    except Exception as e:
        logger.error(f"Score log creation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while creating score log"
        )


@router.get("/score-logs", response_model=GameScoreLogListResponse)
async def get_score_logs(
    user_id: Optional[UUID] = Query(None, description="Filter by user ID"),
    game_id: Optional[UUID] = Query(None, description="Filter by game ID"), 
    content_id: Optional[UUID] = Query(None, description="Filter by content ID"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get game score logs with optional filtering"""
    try:
        logs, total = GameService.get_score_logs(
            db, user_id=user_id, game_id=game_id, content_id=content_id, 
            page=page, per_page=per_page
        )
        
        total_pages = (total + per_page - 1) // per_page
        
        log_responses = [GameScoreLogResponse(**log) if isinstance(log, dict) else GameScoreLogResponse.from_orm(log) for log in logs]
        
        return GameScoreLogListResponse(
            logs=log_responses,
            total=total,
            page=page,
            per_page=per_page,
            total_pages=total_pages
        )
        
    except Exception as e:
        logger.error(f"Get score logs error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while fetching score logs"
        )


@router.get("/users/{user_id}/score-logs", response_model=GameScoreLogListResponse)
async def get_user_score_logs(
    user_id: UUID,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all score logs for a specific user"""
    try:
        logs, total = GameService.get_user_score_logs(db, user_id, page, per_page)
        
        total_pages = (total + per_page - 1) // per_page
        
        log_responses = [GameScoreLogResponse(**log) if isinstance(log, dict) else GameScoreLogResponse.from_orm(log) for log in logs]
        
        return GameScoreLogListResponse(
            logs=log_responses,
            total=total,
            page=page,
            per_page=per_page,
            total_pages=total_pages
        )
        
    except Exception as e:
        logger.error(f"Get user score logs error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while fetching user score logs"
        )


@router.get("/{game_id}/leaderboard-from-logs")
async def get_game_leaderboard_from_logs(
    game_id: UUID,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get leaderboard for a specific game using highest scores from logs"""
    try:
        # Verify game exists
        game = GameService.get_game_by_id(db, game_id)
        if not game:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Game not found"
            )
        
        leaderboard_data, total = GameService.get_game_leaderboard_from_logs(db, game_id, page, per_page)
        
        total_pages = (total + per_page - 1) // per_page
        
        return {
            "leaderboard": leaderboard_data,
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get game leaderboard from logs error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while fetching game leaderboard"
        )


@router.get("/latest-played-from-logs", response_model=LatestGamesPlayedListResponse)
async def get_latest_games_played_from_logs(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get latest unique games played by the current user from score logs"""
    try:
        games_data, total = GameService.get_latest_games_played_from_logs(
            db, current_user.id, page, per_page
        )
        
        total_pages = (total + per_page - 1) // per_page
        
        # Convert dict data to Pydantic models
        games = [LatestGamePlayedResponse(**game_data) for game_data in games_data]
        
        return LatestGamesPlayedListResponse(
            games=games,
            total=total,
            page=page,
            per_page=per_page,
            total_pages=total_pages
        )
        
    except Exception as e:
        logger.error(f"Get latest games played from logs error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while fetching latest games played from logs"
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


@router.get("/scores", response_model=GameScoreListResponse)
async def get_scores(
    user_id: Optional[UUID] = Query(None, description="Filter by user ID"),
    game_id: Optional[UUID] = Query(None, description="Filter by game ID"), 
    content_id: Optional[UUID] = Query(None, description="Filter by content ID"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get game scores with optional filtering"""
    try:
        scores, total = GameService.get_scores(
            db, user_id=user_id, game_id=game_id, content_id=content_id, 
            page=page, per_page=per_page
        )
        
        total_pages = (total + per_page - 1) // per_page
        
        return GameScoreListResponse(
            scores=[GameScoreResponse.from_orm(score) for score in scores],
            total=total,
            page=page,
            per_page=per_page,
            total_pages=total_pages
        )
        
    except Exception as e:
        logger.error(f"Get scores error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while fetching scores"
        )


@router.get("/users/{user_id}/scores", response_model=GameScoreListResponse)
async def get_user_scores(
    user_id: UUID,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all scores for a specific user"""
    try:
        scores, total = GameService.get_user_scores(db, user_id, page, per_page)
        
        total_pages = (total + per_page - 1) // per_page
        
        return GameScoreListResponse(
            scores=[GameScoreResponse.from_orm(score) for score in scores],
            total=total,
            page=page,
            per_page=per_page,
            total_pages=total_pages
        )
        
    except Exception as e:
        logger.error(f"Get user scores error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while fetching user scores"
        )


@router.get("/{game_id}/leaderboard", response_model=GameScoreListResponse)
async def get_game_leaderboard(
    game_id: UUID,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get leaderboard for a specific game"""
    try:
        # Verify game exists
        game = GameService.get_game_by_id(db, game_id)
        if not game:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Game not found"
            )
        
        scores, total = GameService.get_game_leaderboard(db, game_id, page, per_page)
        
        total_pages = (total + per_page - 1) // per_page
        
        return GameScoreListResponse(
            scores=[GameScoreResponse.from_orm(score) for score in scores],
            total=total,
            page=page,
            per_page=per_page,
            total_pages=total_pages
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get game leaderboard error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while fetching game leaderboard"
        )


@router.get("/content/{content_id}/leaderboard", response_model=GameScoreListResponse)
async def get_content_leaderboard(
    content_id: UUID,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get leaderboard for specific content"""
    try:
        scores, total = GameService.get_content_leaderboard(db, content_id, page, per_page)
        
        total_pages = (total + per_page - 1) // per_page
        
        return GameScoreListResponse(
            scores=[GameScoreResponse.from_orm(score) for score in scores],
            total=total,
            page=page,
            per_page=per_page,
            total_pages=total_pages
        )
        
    except Exception as e:
        logger.error(f"Get content leaderboard error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while fetching content leaderboard"
        )


