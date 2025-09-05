from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from uuid import UUID
from app.schemas.auth import UserResponse
from app.schemas.content import ContentResponse
from app.schemas.game import GameResponse


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=100)
    page: int = Field(1, ge=1)
    per_page: int = Field(20, ge=1, le=100)
    include_users: bool = True
    include_content: bool = True
    include_games: bool = True


class SearchResultItem(BaseModel):
    type: str  # 'user', 'content', 'game'
    relevance_score: Optional[float] = None
    data: dict
    
    class Config:
        from_attributes = True


class UnifiedSearchResponse(BaseModel):
    query: str
    users: List[UserResponse]
    content: List[ContentResponse] 
    games: List[GameResponse]
    total_users: int
    total_content: int
    total_games: int
    page: int
    per_page: int
    
    class Config:
        from_attributes = True