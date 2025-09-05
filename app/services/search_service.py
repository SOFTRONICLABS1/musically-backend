from sqlalchemy.orm import Session
from sqlalchemy import or_, desc
from typing import Tuple, List
from app.models.user import User, Content, Game
from app.schemas.search import SearchRequest
import logging

logger = logging.getLogger(__name__)


class SearchService:
    """
    Unified search service for searching across users, content, and games.
    
    Search fields for each entity:
    - Users: username, signup_username, email, bio, instruments_taught, teaching_style, location
    - Content: title, description, tags
    - Games: title, description
    """
    
    @staticmethod
    def search_users(db: Session, query: str, page: int = 1, per_page: int = 20) -> Tuple[List[User], int]:
        """
        Search users by:
        - username
        - signup_username (OAuth provider name)
        - email
        - bio
        - instruments_taught
        - teaching_style
        - location
        """
        search_term = f"%{query.lower()}%"
        
        search_query = db.query(User).filter(
            or_(
                User.username.ilike(search_term),
                User.signup_username.ilike(search_term),
                User.email.ilike(search_term),
                User.bio.ilike(search_term),
                User.instruments_taught.ilike(search_term),
                User.teaching_style.ilike(search_term),
                User.location.ilike(search_term)
            )
        )
        
        # Get total count
        total = search_query.count()
        
        # Apply pagination and ordering
        search_query = search_query.order_by(desc(User.created_at))
        search_query = search_query.offset((page - 1) * per_page)
        search_query = search_query.limit(per_page)
        
        return search_query.all(), total
    
    @staticmethod
    def search_content(db: Session, query: str, page: int = 1, per_page: int = 20) -> Tuple[List[Content], int]:
        """
        Search content by:
        - title
        - description
        - tags (array field)
        """
        search_term = f"%{query.lower()}%"
        
        # For tags, we use the any() operator for array search
        from sqlalchemy.sql import func
        search_query = db.query(Content).filter(
            or_(
                Content.title.ilike(search_term),
                Content.description.ilike(search_term),
                func.array_to_string(Content.tags, ',').ilike(search_term)
            )
        ).filter(Content.is_public == True)  # Only search public content
        
        # Get total count
        total = search_query.count()
        
        # Apply pagination and ordering
        search_query = search_query.order_by(desc(Content.created_at))
        search_query = search_query.offset((page - 1) * per_page)
        search_query = search_query.limit(per_page)
        
        return search_query.all(), total
    
    @staticmethod  
    def search_games(db: Session, query: str, page: int = 1, per_page: int = 20) -> Tuple[List[Game], int]:
        """
        Search games by:
        - title
        - description
        """
        search_term = f"%{query.lower()}%"
        
        search_query = db.query(Game).filter(
            or_(
                Game.title.ilike(search_term),
                Game.description.ilike(search_term)
            )
        )
        
        # Get total count
        total = search_query.count()
        
        # Apply pagination and ordering
        search_query = search_query.order_by(desc(Game.created_at))
        search_query = search_query.offset((page - 1) * per_page)
        search_query = search_query.limit(per_page)
        
        return search_query.all(), total
    
    @staticmethod
    def unified_search(
        db: Session, 
        search_request: SearchRequest
    ) -> dict:
        """
        Perform unified search across all entities
        """
        results = {
            'query': search_request.query,
            'users': [],
            'content': [],
            'games': [],
            'total_users': 0,
            'total_content': 0,
            'total_games': 0,
            'page': search_request.page,
            'per_page': search_request.per_page
        }
        
        # Search users if requested
        if search_request.include_users:
            users, total_users = SearchService.search_users(
                db, 
                search_request.query,
                search_request.page,
                search_request.per_page
            )
            results['users'] = users
            results['total_users'] = total_users
        
        # Search content if requested
        if search_request.include_content:
            content, total_content = SearchService.search_content(
                db,
                search_request.query,
                search_request.page,
                search_request.per_page
            )
            results['content'] = content
            results['total_content'] = total_content
        
        # Search games if requested  
        if search_request.include_games:
            games, total_games = SearchService.search_games(
                db,
                search_request.query,
                search_request.page,
                search_request.per_page
            )
            results['games'] = games
            results['total_games'] = total_games
        
        return results