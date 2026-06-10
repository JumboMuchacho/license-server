"""add result_code to mpesa_transactions

Revision ID: 335aa93f2ed4  # pragma: allowlist secret
Revises: 94f4bab68a73
Create Date: 2026-06-10 23:43:48.758703

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '335aa93f2ed4' # pragma: allowlist secret
down_revision: Union[str, Sequence[str], None] = '94f4bab68a73'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
