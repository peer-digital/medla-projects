"""update_case_table

Revision ID: f01df3fadcb7
Revises: b4034499bd96
Create Date: 2024-12-17 23:26:17.574919

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f01df3fadcb7'
down_revision: Union[str, None] = 'b4034499bd96'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
