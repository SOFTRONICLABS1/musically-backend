"""Add profile fields to users table

Revision ID: d46e7dd4403b
Revises: 
Create Date: 2025-08-14 18:47:56.051197

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd46e7dd4403b'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new profile fields to users table
    op.add_column('users', sa.Column('instruments_taught', sa.Text(), nullable=True))
    op.add_column('users', sa.Column('years_of_experience', sa.Float(), nullable=True))
    op.add_column('users', sa.Column('teaching_style', sa.Text(), nullable=True))
    op.add_column('users', sa.Column('location', sa.String(length=255), nullable=True))


def downgrade() -> None:
    # Remove profile fields from users table
    op.drop_column('users', 'location')
    op.drop_column('users', 'teaching_style') 
    op.drop_column('users', 'years_of_experience')
    op.drop_column('users', 'instruments_taught')
