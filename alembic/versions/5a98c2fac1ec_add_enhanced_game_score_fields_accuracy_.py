"""Add enhanced game score fields: accuracy, attempts, start_time, end_time, cycles, level_config

Revision ID: 5a98c2fac1ec
Revises: 7d7aef42cd29
Create Date: 2025-09-10 19:27:31.928174

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '5a98c2fac1ec'
down_revision: Union[str, None] = '7d7aef42cd29'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add enhanced game score fields
    op.add_column('game_scores', sa.Column('accuracy', sa.DECIMAL(precision=5, scale=2), nullable=True))
    op.add_column('game_scores', sa.Column('attempts', sa.Integer(), nullable=False, server_default='1'))
    op.add_column('game_scores', sa.Column('start_time', sa.DateTime(), nullable=True))
    op.add_column('game_scores', sa.Column('end_time', sa.DateTime(), nullable=True))
    op.add_column('game_scores', sa.Column('cycles', sa.Integer(), nullable=True))
    op.add_column('game_scores', sa.Column('level_config', postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    # Remove enhanced game score fields
    op.drop_column('game_scores', 'level_config')
    op.drop_column('game_scores', 'cycles')
    op.drop_column('game_scores', 'end_time')
    op.drop_column('game_scores', 'start_time')
    op.drop_column('game_scores', 'attempts')
    op.drop_column('game_scores', 'accuracy')
