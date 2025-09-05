"""add_signup_username_and_make_username_nullable

Revision ID: 554c75177662
Revises: d46e7dd4403b
Create Date: 2025-08-18 15:37:46.172631

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '554c75177662'
down_revision: Union[str, None] = 'd46e7dd4403b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add signup_username column
    op.add_column('users', sa.Column('signup_username', sa.String(length=255), nullable=True))
    
    # Make username column nullable
    op.alter_column('users', 'username',
                    existing_type=sa.String(length=100),
                    nullable=True)


def downgrade() -> None:
    # Make username column non-nullable again
    op.alter_column('users', 'username',
                    existing_type=sa.String(length=100),
                    nullable=False)
    
    # Remove signup_username column
    op.drop_column('users', 'signup_username')
