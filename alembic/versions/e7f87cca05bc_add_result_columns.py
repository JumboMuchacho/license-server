"""add result columns

Revision ID: e7f87cca05bc # pragma: allowlist secret
Revises: edb5e8d02ed6
Create Date: 2026-06-11 05:48:58.228495

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e7f87cca05bc' # pragma: allowlist secret
down_revision: Union[str, Sequence[str], None] = 'edb5e8d02ed6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
