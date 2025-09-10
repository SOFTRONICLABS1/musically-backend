from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc
from typing import List, Optional, Tuple
from uuid import UUID

from app.models.user import Game, ContentGame, Content, User, GameScore
from app.schemas.game import GameCreate, GameUpdate, GameScoreCreate
import logging

logger = logging.getLogger(__name__)


class GameService:
    
    @staticmethod
    def create_game(db: Session, creator_id: UUID, game_data: GameCreate) -> Game:
        """Create a new game"""
        
        db_game = Game(
            creator_id=creator_id,
            title=game_data.title,
            description=game_data.description
        )
        
        db.add(db_game)
        db.commit()
        db.refresh(db_game)
        
        return db_game
    
    @staticmethod
    def get_game_by_id(db: Session, game_id: UUID) -> Optional[Game]:
        """Get game by ID"""
        return db.query(Game).filter(Game.id == game_id).first()
    
    @staticmethod
    def get_all_games(
        db: Session, 
        page: int = 1, 
        per_page: int = 20,
        search: Optional[str] = None
    ) -> Tuple[List[Game], int]:
        """Get all games with pagination and search"""
        
        query = db.query(Game)
        
        # Apply search filter
        if search:
            search_term = f"%{search.lower()}%"
            query = query.filter(
                or_(
                    Game.title.ilike(search_term),
                    Game.description.ilike(search_term)
                )
            )
        
        # Get total count
        total = query.count()
        
        # Apply pagination and ordering
        query = query.order_by(desc(Game.created_at))
        query = query.offset((page - 1) * per_page)
        query = query.limit(per_page)
        
        return query.all(), total
    
    @staticmethod
    def get_user_games(
        db: Session, 
        creator_id: UUID,
        page: int = 1,
        per_page: int = 20
    ) -> Tuple[List[Game], int]:
        """Get games created by a specific user"""
        
        query = db.query(Game).filter(Game.creator_id == creator_id)
        
        # Get total count
        total = query.count()
        
        # Apply pagination and ordering
        query = query.order_by(desc(Game.created_at))
        query = query.offset((page - 1) * per_page)
        query = query.limit(per_page)
        
        return query.all(), total
    
    @staticmethod
    def update_game(
        db: Session, 
        game_id: UUID, 
        creator_id: UUID, 
        update_data: GameUpdate
    ) -> Optional[Game]:
        """Update game owned by creator"""
        
        game = db.query(Game).filter(
            and_(
                Game.id == game_id,
                Game.creator_id == creator_id
            )
        ).first()
        
        if not game:
            return None
        
        # Update only provided fields
        update_dict = update_data.dict(exclude_unset=True)
        
        for field, value in update_dict.items():
            setattr(game, field, value)
        
        # Update timestamp
        from datetime import datetime
        game.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(game)
        
        return game
    
    @staticmethod
    def delete_game(db: Session, game_id: UUID, creator_id: UUID) -> bool:
        """Delete game owned by creator"""
        
        game = db.query(Game).filter(
            and_(
                Game.id == game_id,
                Game.creator_id == creator_id
            )
        ).first()
        
        if not game:
            return False
        
        db.delete(game)
        db.commit()
        
        return True
    
    @staticmethod
    def add_content_to_game(db: Session, content_id: UUID, game_id: UUID, user_id: UUID) -> Optional[ContentGame]:
        """Add content to game (user must own the content)"""
        
        # Verify content ownership
        content = db.query(Content).filter(
            and_(
                Content.id == content_id,
                Content.user_id == user_id
            )
        ).first()
        
        if not content:
            return None
        
        # Verify game exists
        game = db.query(Game).filter(Game.id == game_id).first()
        if not game:
            return None
        
        # Check if association already exists
        existing = db.query(ContentGame).filter(
            and_(
                ContentGame.content_id == content_id,
                ContentGame.game_id == game_id
            )
        ).first()
        
        if existing:
            return existing
        
        # Create new association
        content_game = ContentGame(
            content_id=content_id,
            game_id=game_id
        )
        
        db.add(content_game)
        db.commit()
        db.refresh(content_game)
        
        return content_game
    
    @staticmethod
    def remove_content_from_game(db: Session, content_id: UUID, game_id: UUID, user_id: UUID) -> bool:
        """Remove content from game (user must own the content)"""
        
        # Verify content ownership
        content = db.query(Content).filter(
            and_(
                Content.id == content_id,
                Content.user_id == user_id
            )
        ).first()
        
        if not content:
            return False
        
        # Find and delete association
        content_game = db.query(ContentGame).filter(
            and_(
                ContentGame.content_id == content_id,
                ContentGame.game_id == game_id
            )
        ).first()
        
        if not content_game:
            return False
        
        db.delete(content_game)
        db.commit()
        
        return True
    
    @staticmethod
    def get_game_content(db: Session, game_id: UUID, page: int = 1, per_page: int = 20) -> Tuple[List[Content], int]:
        """Get all content associated with a game"""
        
        query = db.query(Content).join(ContentGame).filter(ContentGame.game_id == game_id)
        
        # Get total count
        total = query.count()
        
        # Apply pagination and ordering
        query = query.order_by(desc(Content.created_at))
        query = query.offset((page - 1) * per_page)
        query = query.limit(per_page)
        
        return query.all(), total
    
    @staticmethod
    def get_content_games(db: Session, content_id: UUID, page: int = 1, per_page: int = 20) -> Tuple[List[Game], int]:
        """Get all games associated with content"""
        
        query = db.query(Game).join(ContentGame).filter(ContentGame.content_id == content_id)
        
        # Get total count
        total = query.count()
        
        # Apply pagination and ordering
        query = query.order_by(desc(Game.created_at))
        query = query.offset((page - 1) * per_page)
        query = query.limit(per_page)
        
        return query.all(), total
    
    @staticmethod
    def increment_play_count(db: Session, game_id: UUID) -> bool:
        """Increment play count for game"""
        
        game = db.query(Game).filter(Game.id == game_id).first()
        if not game:
            return False
        
        game.play_count += 1
        db.commit()
        
        return True
    
    @staticmethod
    def increment_content_game_play_count(db: Session, content_id: UUID, game_id: UUID) -> bool:
        """Increment play count for content-game pair"""
        
        content_game = db.query(ContentGame).filter(
            and_(
                ContentGame.content_id == content_id,
                ContentGame.game_id == game_id
            )
        ).first()
        
        if not content_game:
            return False
        
        content_game.play_count += 1
        
        # Also increment the overall game play count
        game = db.query(Game).filter(Game.id == game_id).first()
        if game:
            game.play_count += 1
        
        db.commit()
        
        return True
    
    @staticmethod
    def publish_game(db: Session, game_id: UUID, creator_id: UUID) -> bool:
        """Publish a game owned by creator"""
        
        game = db.query(Game).filter(
            and_(
                Game.id == game_id,
                Game.creator_id == creator_id
            )
        ).first()
        
        if not game:
            return False
        
        game.is_published = True
        from datetime import datetime
        game.updated_at = datetime.utcnow()
        db.commit()
        
        return True
    
    @staticmethod
    def unpublish_game(db: Session, game_id: UUID, creator_id: UUID) -> bool:
        """Unpublish a game owned by creator"""
        
        game = db.query(Game).filter(
            and_(
                Game.id == game_id,
                Game.creator_id == creator_id
            )
        ).first()
        
        if not game:
            return False
        
        game.is_published = False
        from datetime import datetime
        game.updated_at = datetime.utcnow()
        db.commit()
        
        return True
    
    @staticmethod
    def record_score(db: Session, user_id: UUID, score_data: GameScoreCreate) -> Optional[GameScore]:
        """Record a game score for user-game-content combination"""
        
        # Verify game exists
        game = db.query(Game).filter(Game.id == score_data.game_id).first()
        if not game:
            return None
        
        # Verify content exists
        content = db.query(Content).filter(Content.id == score_data.content_id).first()
        if not content:
            return None
        
        # Check if score already exists for this combination
        existing_score = db.query(GameScore).filter(
            and_(
                GameScore.user_id == user_id,
                GameScore.game_id == score_data.game_id,
                GameScore.content_id == score_data.content_id
            )
        ).first()
        
        if existing_score:
            # Update existing score if new score is better
            if score_data.score > existing_score.score:
                existing_score.score = score_data.score
                from datetime import datetime
                existing_score.created_at = datetime.utcnow()
                db.commit()
                db.refresh(existing_score)
            return existing_score
        else:
            # Create new score record
            game_score = GameScore(
                user_id=user_id,
                game_id=score_data.game_id,
                content_id=score_data.content_id,
                score=score_data.score
            )
            
            db.add(game_score)
            db.commit()
            db.refresh(game_score)
            
            return game_score

    @staticmethod
    def get_scores(
        db: Session, 
        user_id: Optional[UUID] = None,
        game_id: Optional[UUID] = None,
        content_id: Optional[UUID] = None,
        page: int = 1,
        per_page: int = 20
    ) -> Tuple[List[GameScore], int]:
        """Get game scores with optional filtering"""
        query = db.query(GameScore)
        
        # Apply filters
        if user_id:
            query = query.filter(GameScore.user_id == user_id)
        if game_id:
            query = query.filter(GameScore.game_id == game_id)
        if content_id:
            query = query.filter(GameScore.content_id == content_id)
        
        # Get total count
        total = query.count()
        
        # Apply pagination and ordering (highest scores first, then most recent)
        scores = query.order_by(GameScore.score.desc(), GameScore.created_at.desc())\
                      .offset((page - 1) * per_page)\
                      .limit(per_page)\
                      .all()
        
        return scores, total

    @staticmethod
    def get_user_scores(db: Session, user_id: UUID, page: int = 1, per_page: int = 20) -> Tuple[List[GameScore], int]:
        """Get all scores for a specific user"""
        return GameService.get_scores(db, user_id=user_id, page=page, per_page=per_page)

    @staticmethod
    def get_game_leaderboard(db: Session, game_id: UUID, page: int = 1, per_page: int = 20) -> Tuple[List[GameScore], int]:
        """Get leaderboard for a specific game (top scores across all content)"""
        return GameService.get_scores(db, game_id=game_id, page=page, per_page=per_page)

    @staticmethod
    def get_content_leaderboard(db: Session, content_id: UUID, page: int = 1, per_page: int = 20) -> Tuple[List[GameScore], int]:
        """Get leaderboard for specific content within a game"""
        return GameService.get_scores(db, content_id=content_id, page=page, per_page=per_page)

    @staticmethod
    def get_latest_games_played(db: Session, user_id: UUID, page: int = 1, per_page: int = 20) -> Tuple[List[Dict], int]:
        """Get latest unique games played by user (most recent play per game)"""
        from sqlalchemy import func, desc
        from app.models.user import Content
        
        # Create a subquery to get the latest score for each game by the user
        latest_scores_subquery = db.query(
            GameScore.game_id,
            func.max(GameScore.created_at).label('latest_play_time')
        ).filter(
            GameScore.user_id == user_id
        ).group_by(GameScore.game_id).subquery()
        
        # Join with the main query to get full details of the latest plays
        query = db.query(
            GameScore.game_id,
            Game.title.label('game_name'),
            GameScore.content_id,
            Content.title.label('content_name'),
            GameScore.score,
            GameScore.created_at.label('last_played_time')
        ).join(
            Game, GameScore.game_id == Game.id
        ).join(
            Content, GameScore.content_id == Content.id
        ).join(
            latest_scores_subquery,
            (GameScore.game_id == latest_scores_subquery.c.game_id) &
            (GameScore.created_at == latest_scores_subquery.c.latest_play_time)
        ).filter(
            GameScore.user_id == user_id
        ).order_by(desc(GameScore.created_at))
        
        # Get total count
        total = query.count()
        
        # Apply pagination
        results = query.offset((page - 1) * per_page).limit(per_page).all()
        
        # Convert to dictionaries
        games_data = []
        for result in results:
            games_data.append({
                'game_id': result.game_id,
                'game_name': result.game_name,
                'content_id': result.content_id,
                'content_name': result.content_name,
                'score': float(result.score),
                'last_played_time': result.last_played_time
            })
        
        return games_data, total