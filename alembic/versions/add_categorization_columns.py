"""add categorization columns

Revision ID: add_categorization_columns
Revises: 00f636dc84ae
Create Date: 2023-12-16 23:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_categorization_columns'
down_revision = '00f636dc84ae'
branch_labels = None
depends_on = None


def upgrade():
    # Add new columns for categorization
    op.add_column('cases', sa.Column('primary_category', sa.String(), nullable=True))
    op.add_column('cases', sa.Column('sub_category', sa.String(), nullable=True))
    op.add_column('cases', sa.Column('category_confidence', sa.Float(), nullable=True))
    op.add_column('cases', sa.Column('category_version', sa.Integer(), nullable=True))
    op.add_column('cases', sa.Column('category_metadata', sa.JSON(), nullable=True))
    op.add_column('cases', sa.Column('last_categorized_at', sa.DateTime(timezone=True), nullable=True))


def downgrade():
    # Remove the categorization columns
    op.drop_column('cases', 'last_categorized_at')
    op.drop_column('cases', 'category_metadata')
    op.drop_column('cases', 'category_version')
    op.drop_column('cases', 'category_confidence')
    op.drop_column('cases', 'sub_category')
    op.drop_column('cases', 'primary_category') 