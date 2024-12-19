"""Add case detail fields

Revision ID: 899562313900
Revises: 00f636dc84ae
Create Date: 2024-12-01 21:45:12.658551

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '899562313900'
down_revision: Union[str, None] = '00f636dc84ae'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('cases', sa.Column('sender', sa.String(), nullable=True))
    op.add_column('cases', sa.Column('decision_date', sa.DateTime(), nullable=True))
    op.add_column('cases', sa.Column('decision_summary', sa.Text(), nullable=True))
    op.add_column('cases', sa.Column('case_type', sa.String(), nullable=True))
    op.add_column('cases', sa.Column('documents', sa.JSON(), nullable=True))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('cases', 'documents')
    op.drop_column('cases', 'case_type')
    op.drop_column('cases', 'decision_summary')
    op.drop_column('cases', 'decision_date')
    op.drop_column('cases', 'sender')
    # ### end Alembic commands ###