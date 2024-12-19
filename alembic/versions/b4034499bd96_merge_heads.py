"""merge heads

Revision ID: b4034499bd96
Revises: 3722c60e9799, add_categorization_columns
Create Date: 2024-12-17 23:26:01.514462

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b4034499bd96'
down_revision: Union[str, None] = ('3722c60e9799', 'add_categorization_columns')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
