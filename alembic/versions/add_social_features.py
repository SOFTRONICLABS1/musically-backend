"""Add follows and content_likes tables for social features

Revision ID: add_social_features
Revises: d46e7dd4403b
Create Date: 2025-01-28

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_social_features'
down_revision = 'd46e7dd4403b'
branch_labels = None
depends_on = None


def upgrade():
    # Create follows table
    op.create_table('follows',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('follower_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('following_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['follower_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['following_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create index for follows table
    op.create_index('ix_follows_follower_id', 'follows', ['follower_id'])
    op.create_index('ix_follows_following_id', 'follows', ['following_id'])
    op.create_index('ix_follows_follower_following', 'follows', ['follower_id', 'following_id'], unique=True)
    
    # Create content_likes table
    op.create_table('content_likes',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('content_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['content_id'], ['content.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create index for content_likes table
    op.create_index('ix_content_likes_user_id', 'content_likes', ['user_id'])
    op.create_index('ix_content_likes_content_id', 'content_likes', ['content_id'])
    op.create_index('ix_content_likes_user_content', 'content_likes', ['user_id', 'content_id'], unique=True)


def downgrade():
    # Drop content_likes table and indexes
    op.drop_index('ix_content_likes_user_content', table_name='content_likes')
    op.drop_index('ix_content_likes_content_id', table_name='content_likes')
    op.drop_index('ix_content_likes_user_id', table_name='content_likes')
    op.drop_table('content_likes')
    
    # Drop follows table and indexes
    op.drop_index('ix_follows_follower_following', table_name='follows')
    op.drop_index('ix_follows_following_id', table_name='follows')
    op.drop_index('ix_follows_follower_id', table_name='follows')
    op.drop_table('follows')