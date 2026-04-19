
"""add citations to messages

Revision ID: a7be89d7bf96
Revises: a1b2c3d4e5f6
Create Date: 2026-04-19 16:26:32.093964

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a7be89d7bf96'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # vec_* tables are managed by PgVectorStore at runtime, not by Alembic — do not touch them
    op.add_column('messages', sa.Column('citations', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'))


def downgrade() -> None:
    op.drop_column('messages', 'citations')
