from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID


class GameBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    thumbnail: Optional[str] = Field(None, description="Base64 encoded image")


class GameCreate(GameBase):
    pass


class GameUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    thumbnail: Optional[str] = Field(None, description="Base64 encoded image")
    is_published: Optional[bool] = None


class GameResponse(GameBase):
    id: UUID
    creator_id: UUID
    is_published: bool
    play_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class GameListResponse(BaseModel):
    games: List[GameResponse]
    total: int
    page: int
    per_page: int
    total_pages: int


class ContentGameCreate(BaseModel):
    content_id: UUID
    game_id: UUID


class ContentGameResponse(BaseModel):
    id: UUID
    content_id: UUID
    game_id: UUID
    play_count: int
    created_at: datetime

    class Config:
        from_attributes = True


class GameWithContentResponse(GameResponse):
    content_count: int = 0


class ContentWithGamesResponse(BaseModel):
    content_id: UUID
    games: List[GameResponse]
    total: int
    page: int
    per_page: int
    total_pages: int


class GameScoreCreate(BaseModel):
    game_id: UUID
    content_id: UUID
    score: float = Field(..., ge=0)
    accuracy: Optional[float] = Field(None, ge=0, le=100, description="Accuracy percentage (0-100)")
    
    # High score metadata (only saved when achieving highest score)
    start_time: Optional[datetime] = Field(None, description="Game start time")
    end_time: Optional[datetime] = Field(None, description="Game end time") 
    cycles: Optional[int] = Field(None, ge=0, description="Number of cycles")
    level_config: Optional[Dict[str, Any]] = Field(None, description="Level configuration JSON")


class GameScoreResponse(BaseModel):
    id: UUID
    user_id: UUID
    game_id: UUID
    content_id: UUID
    score: float
    accuracy: Optional[float]
    attempts: int
    
    # High score metadata (only present when this is the highest score)
    start_time: Optional[datetime]
    end_time: Optional[datetime] 
    cycles: Optional[int]
    level_config: Optional[Dict[str, Any]]
    
    created_at: datetime

    class Config:
        from_attributes = True


class GameScoreListResponse(BaseModel):
    scores: List[GameScoreResponse]
    total: int
    page: int
    per_page: int
    total_pages: int


class LatestGamePlayedResponse(BaseModel):
    game_id: UUID
    game_name: str
    content_id: UUID
    content_name: str
    score: float
    last_played_time: datetime

    class Config:
        from_attributes = True


class LatestGamesPlayedListResponse(BaseModel):
    games: List[LatestGamePlayedResponse]
    total: int
    page: int
    per_page: int
    total_pages: int


class GameScoreLogCreate(BaseModel):
    game_id: UUID
    content_id: UUID
    score: float = Field(..., ge=0)
    accuracy: Optional[float] = Field(None, ge=0, le=100, description="Accuracy percentage (0-100)")
    attempts: int = Field(1, ge=1, description="Attempt number for this session")
    
    # Game session metadata
    start_time: Optional[datetime] = Field(None, description="Game start time")
    end_time: Optional[datetime] = Field(None, description="Game end time") 
    cycles: Optional[int] = Field(None, ge=0, description="Number of cycles")
    level_config: Optional[Dict[str, Any]] = Field(None, description="Level configuration JSON")


class GameScoreLogResponse(BaseModel):
    id: UUID
    user_id: UUID
    game_id: UUID
    content_id: UUID
    score: float
    accuracy: Optional[float]
    attempts: int
    
    # Game session metadata
    start_time: Optional[datetime]
    end_time: Optional[datetime] 
    cycles: Optional[int]
    level_config: Optional[Dict[str, Any]]
    
    created_at: datetime

    class Config:
        from_attributes = True


class GameScoreLogListResponse(BaseModel):
    logs: List[GameScoreLogResponse]
    total: int
    page: int
    per_page: int
    total_pages: int