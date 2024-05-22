"""Alter assignment deadline to timestamptz.

Revision ID: b8d8eafb9ab7
Revises: 1ccd1805bf48
Create Date: 2024-05-22 14:36:45.990339

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b8d8eafb9ab7"
down_revision: Union[str, None] = "1ccd1805bf48"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column(
        "assignment",
        "deadline",
        existing_type=postgresql.TIMESTAMP(),
        type_=sa.TIMESTAMP(timezone=True),
        existing_nullable=True,
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column(
        "assignment",
        "deadline",
        existing_type=sa.TIMESTAMP(timezone=True),
        type_=postgresql.TIMESTAMP(),
        existing_nullable=True,
    )
    # ### end Alembic commands ###