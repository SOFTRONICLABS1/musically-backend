from sqlalchemy import Column, String, Boolean, Integer, Float, DateTime, ForeignKey, Text, ARRAY, DECIMAL, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.db.database import Base
import uuid
from datetime import datetime


class User(Base):
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), unique=True, nullable=True, index=True)
    signup_username = Column(String(255), nullable=True)  # Name from OAuth provider
    gender = Column(String(20), nullable=False)
    phone_number = Column(String(20), nullable=True)
    country_code = Column(String(5), nullable=True)
    bio = Column(Text, nullable=True)
    profile_image_url = Column(String(500), nullable=True)
    instruments_taught = Column(Text, nullable=True)  # JSON array of instruments
    years_of_experience = Column(Float, nullable=True)
    teaching_style = Column(Text, nullable=True)
    location = Column(String(255), nullable=True)
    is_verified = Column(Boolean, default=False)
    subscription_tier = Column(String(50), default="free")
    total_subscribers = Column(Integer, default=0)
    total_content_created = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    auth_users = relationship("AuthUser", back_populates="user", cascade="all, delete-orphan")
    content = relationship("Content", back_populates="user", cascade="all, delete-orphan")
    games = relationship("Game", back_populates="creator", cascade="all, delete-orphan")


class AuthUser(Base):
    __tablename__ = "auth_users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    auth_provider = Column(String(50), nullable=False)  # 'local', 'google', 'apple'
    provider_user_id = Column(String(255), nullable=True)  # ID from OAuth provider
    email = Column(String(255), nullable=False)
    password_hash = Column(String(255), nullable=True)  # Only for local auth
    is_email_verified = Column(Boolean, default=False)
    last_login = Column(DateTime, nullable=True)
    refresh_token = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="auth_users")


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token = Column(String(255), nullable=False, unique=True)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Content(Base):
    __tablename__ = "content"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # Content type and location
    content_type = Column(String(20), nullable=False)  # 'media_file', 'social_link', 'notes_only'
    media_url = Column(String(500), nullable=True)  # For uploaded files
    media_type = Column(String(50), nullable=True)  # 'audio', 'video'
    social_url = Column(String(500), nullable=True)  # For social media links
    social_platform = Column(String(50), nullable=True)  # 'youtube', 'facebook', 'instagram', 'linkedin'
    
    # Musical content data
    notes_data = Column(JSONB, nullable=True)  # Musical notes data
    tempo = Column(Integer, nullable=True)  # BPM
    
    # Access and visibility
    is_public = Column(Boolean, default=True)
    access_type = Column(String(20), default='free')  # 'free', 'subscribers_only', 'playlist_only'
    tags = Column(ARRAY(Text), nullable=True)
    
    # Metrics
    play_count = Column(Integer, default=0)
    avg_score = Column(DECIMAL(5,2), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="content")
    likes = relationship("ContentLike", back_populates="content", cascade="all, delete-orphan")


class Follow(Base):
    __tablename__ = "follows"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    follower_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    following_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    follower = relationship("User", foreign_keys=[follower_id], backref="following_relations")
    following = relationship("User", foreign_keys=[following_id], backref="follower_relations")


class ContentLike(Base):
    __tablename__ = "content_likes"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    content_id = Column(UUID(as_uuid=True), ForeignKey("content.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", backref="content_likes")
    content = relationship("Content", back_populates="likes")


class Game(Base):
    __tablename__ = "games"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    thumbnail = Column(Text, nullable=True)
    creator_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    is_published = Column(Boolean, default=False)
    play_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    creator = relationship("User", back_populates="games")
    content_games = relationship("ContentGame", back_populates="game", cascade="all, delete-orphan")
    game_scores = relationship("GameScore", back_populates="game", cascade="all, delete-orphan")


class ContentGame(Base):
    __tablename__ = "content_games"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    content_id = Column(UUID(as_uuid=True), ForeignKey("content.id", ondelete="CASCADE"), nullable=False)
    game_id = Column(UUID(as_uuid=True), ForeignKey("games.id", ondelete="CASCADE"), nullable=False)
    play_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    content = relationship("Content", backref="content_games")
    game = relationship("Game", back_populates="content_games")


class GameScore(Base):
    __tablename__ = "game_scores"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    game_id = Column(UUID(as_uuid=True), ForeignKey("games.id", ondelete="CASCADE"), nullable=False)
    content_id = Column(UUID(as_uuid=True), ForeignKey("content.id", ondelete="CASCADE"), nullable=False)
    score = Column(DECIMAL(10,2), nullable=False)
    accuracy = Column(DECIMAL(5,2), nullable=True)  # Percentage accuracy (0-100)
    attempts = Column(Integer, default=1, nullable=False)  # Auto-increments on each API hit
    
    # High score metadata (only stored when achieving highest score)
    start_time = Column(DateTime, nullable=True)  # Game start time for high score
    end_time = Column(DateTime, nullable=True)  # Game end time for high score
    cycles = Column(Integer, nullable=True)  # Custom cycles count for high score
    level_config = Column(JSONB, nullable=True)  # {"level": "hard", "BPM": 120}
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", backref="game_scores")
    game = relationship("Game", back_populates="game_scores")
    content = relationship("Content", backref="game_scores")


class AdminUser(Base):
    __tablename__ = "admin_users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default="content_moderator")  # super_admin, content_moderator, user_manager, analytics_viewer
    permissions = Column(JSONB, nullable=True)  # Array of specific permissions
    is_active = Column(Boolean, default=True)
    last_login = Column(DateTime, nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("admin_users.id"), nullable=True)  # Admin who created this admin
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Self-referential relationship for created_by
    creator = relationship("AdminUser", remote_side=[id], backref="created_admins")


class UserSubscription(Base):
    __tablename__ = "user_subscriptions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)  # User being subscribed to
    subscriber_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)  # User who is subscribing
    subscription_type = Column(String(50), default="basic")  # basic, premium, etc.
    is_active = Column(Boolean, default=True)
    subscribed_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)  # For time-limited subscriptions
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    owner = relationship("User", foreign_keys=[owner_user_id], backref="subscribers")
    subscriber = relationship("User", foreign_keys=[subscriber_user_id], backref="subscriptions")
    
    # Unique constraint to prevent duplicate subscriptions
    __table_args__ = (
        UniqueConstraint('owner_user_id', 'subscriber_user_id', name='unique_subscription'),
    )


class GameScoreLog(Base):
    __tablename__ = "game_score_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    game_id = Column(UUID(as_uuid=True), ForeignKey("games.id", ondelete="CASCADE"), nullable=False)
    content_id = Column(UUID(as_uuid=True), ForeignKey("content.id", ondelete="CASCADE"), nullable=False)
    score = Column(DECIMAL(10,2), nullable=False)
    accuracy = Column(DECIMAL(5,2), nullable=True)  # Percentage accuracy (0-100)
    attempts = Column(Integer, default=1, nullable=False)  # Can track session attempt number
    
    # Game session metadata
    start_time = Column(DateTime, nullable=True)  # Game start time
    end_time = Column(DateTime, nullable=True)  # Game end time
    cycles = Column(Integer, nullable=True)  # Custom cycles count
    level_config = Column(JSONB, nullable=True)  # {"level": "hard", "BPM": 120}
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", backref="game_score_logs")
    game = relationship("Game", backref="game_score_logs") 
    content = relationship("Content", backref="game_score_logs")
    
    # Partitioning configuration - will be handled in migration
    __table_args__ = (
        # Add indexes for common query patterns
        # Primary queries: user_id, game_id, content_id, created_at
    )