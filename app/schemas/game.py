from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID


class GameBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)


class GameCreate(GameBase):
    pass


class GameUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
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


class GameScoreResponse(BaseModel):
    id: UUID
    user_id: UUID
    game_id: UUID
    content_id: UUID
    score: float
    created_at: datetime

    class Config:
        from_attributes = True