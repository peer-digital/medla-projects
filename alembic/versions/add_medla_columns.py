"""add medla columns

Revision ID: add_medla_columns
Revises: add_categorization_columns
Create Date: 2023-12-17 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_medla_columns'
down_revision = 'add_categorization_columns'
branch_labels = None
depends_on = None


def upgrade():
    # Add new columns for Medla-specific data
    op.add_column('cases', sa.Column('project_phase', sa.String(), nullable=True))
    op.add_column('cases', sa.Column('is_medla_suitable', sa.Boolean(), nullable=True))
    op.add_column('cases', sa.Column('potential_jobs', sa.JSON(), nullable=True))


def downgrade():
    # Remove the Medla-specific columns
    op.drop_column('cases', 'potential_jobs')
    op.drop_column('cases', 'is_medla_suitable')
    op.drop_column('cases', 'project_phase') 