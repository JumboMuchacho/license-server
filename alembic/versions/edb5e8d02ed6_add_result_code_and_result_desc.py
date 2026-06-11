"""add result_code and result_desc

Revision ID: edb5e8d02ed6
Revises: 8ad077b56c6b
Create Date: 2026-06-11 01:49:37.905410

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'edb5e8d02ed6'# pragma: allowlist secret
down_revision: Union[str, Sequence[str], None] = '8ad077b56c6b'# pragma: allowlist secret
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
