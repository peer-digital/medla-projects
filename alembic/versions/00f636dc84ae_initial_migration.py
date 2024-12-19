"""Initial migration

Revision ID: 00f636dc84ae
Revises: 
Create Date: 2024-12-01 21:21:58.495365

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '00f636dc84ae'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('cases',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('title', sa.String(), nullable=False),
    sa.Column('date', sa.DateTime(), nullable=False),
    sa.Column('location', sa.String(), nullable=True),
    sa.Column('municipality', sa.String(), nullable=True),
    sa.Column('status', sa.String(), nullable=True),
    sa.Column('url', sa.String(), nullable=True),
    sa.Column('lan', sa.String(), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('bookmarks',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('case_id', sa.String(), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('is_green_industry', sa.Boolean(), nullable=True),
    sa.Column('industry_type', sa.String(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_bookmarks_id'), 'bookmarks', ['id'], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_bookmarks_id'), table_name='bookmarks')
    op.drop_table('bookmarks')
    op.drop_table('cases')
    # ### end Alembic commands ###