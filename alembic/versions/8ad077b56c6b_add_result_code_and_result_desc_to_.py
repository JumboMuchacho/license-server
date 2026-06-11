"""add result_code and result_desc to mpesa_transactions

Revision ID: 8ad077b56c6b # pragma: allowlist secret
Revises: 335aa93f2ed4
Create Date: 2026-06-11 01:27:13.913825

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8ad077b56c6b' # pragma: allowlist secret
down_revision: Union[str, Sequence[str], None] = '335aa93f2ed4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
