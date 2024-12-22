"""merge all changes

Revision ID: merge_all_changes
Revises: f01df3fadcb7, add_medla_columns
Create Date: 2023-12-17 11:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'merge_all_changes'
down_revision = ('f01df3fadcb7', 'add_medla_columns')
branch_labels = None
depends_on = None


def upgrade():
    pass  # All changes are already in the database


def downgrade():
    pass  # No need to downgrade since this is just a merge migration 