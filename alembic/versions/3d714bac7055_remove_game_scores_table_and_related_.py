"""Remove game_scores table and related functionality

Revision ID: 3d714bac7055
Revises: ba8eeb90871a
Create Date: 2025-09-15 14:05:32.967032

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3d714bac7055'
down_revision: Union[str, None] = 'ba8eeb90871a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the game_scores table
    op.drop_table('game_scores')


def downgrade() -> None:
    # Recreate the game_scores table if needed to rollback
    from sqlalchemy.dialects import postgresql
    op.create_table('game_scores',
    sa.Column('id', postgresql.UUID(), autoincrement=False, nullable=False),
    sa.Column('user_id', postgresql.UUID(), autoincrement=False, nullable=False),
    sa.Column('game_id', postgresql.UUID(), autoincrement=False, nullable=False),
    sa.Column('content_id', postgresql.UUID(), autoincrement=False, nullable=False),
    sa.Column('score', sa.NUMERIC(), autoincrement=False, nullable=False),
    sa.Column('accuracy', sa.NUMERIC(), autoincrement=False, nullable=True),
    sa.Column('attempts', sa.INTEGER(), autoincrement=False, nullable=False),
    sa.Column('start_time', postgresql.TIMESTAMP(), autoincrement=False, nullable=True),
    sa.Column('end_time', postgresql.TIMESTAMP(), autoincrement=False, nullable=True),
    sa.Column('cycles', sa.INTEGER(), autoincrement=False, nullable=True),
    sa.Column('level_config', postgresql.JSONB(astext_type=sa.Text()), autoincrement=False, nullable=True),
    sa.Column('created_at', postgresql.TIMESTAMP(), server_default=sa.text('now()'), autoincrement=False, nullable=False),
    sa.ForeignKeyConstraint(['content_id'], ['content.id'], name='game_scores_content_id_fkey'),
    sa.ForeignKeyConstraint(['game_id'], ['games.id'], name='game_scores_game_id_fkey'), 
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='game_scores_user_id_fkey'),
    sa.PrimaryKeyConstraint('id', name='game_scores_pkey'),
    sa.UniqueConstraint('user_id', 'game_id', 'content_id', name='game_scores_user_id_game_id_content_id_key')
    )
