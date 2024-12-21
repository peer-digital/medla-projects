"""add fetch tracking columns

Revision ID: add_fetch_tracking
Revises: f01df3fadcb7
Create Date: 2024-12-21 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_fetch_tracking'
down_revision = 'f01df3fadcb7'
branch_labels = None
depends_on = None


def upgrade():
    # Add new columns for fetch tracking
    op.add_column('cases', sa.Column('last_updated_from_source', sa.DateTime(timezone=True), nullable=True))

    # Create fetch_status table
    op.create_table('fetch_status',
        sa.Column('lan', sa.String(), nullable=False),
        sa.Column('last_successful_fetch', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_page_fetched', sa.Integer(), server_default='0', nullable=False),
        sa.Column('total_pages', sa.Integer(), nullable=True),
        sa.Column('error_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('last_error', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('lan')
    )


def downgrade():
    # Remove fetch tracking columns
    op.drop_column('cases', 'last_updated_from_source')

    # Drop fetch_status table
    op.drop_table('fetch_status') 