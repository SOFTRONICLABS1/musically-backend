"""Merge migration heads

Revision ID: 5c17e29a35be
Revises: 554c75177662, add_social_features
Create Date: 2025-09-01 18:44:28.841730

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5c17e29a35be'
down_revision: Union[str, None] = ('554c75177662', 'add_social_features')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
