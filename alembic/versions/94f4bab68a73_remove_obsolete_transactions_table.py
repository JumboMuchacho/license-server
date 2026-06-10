"""remove obsolete transactions table

Revision ID: 94f4bab68a73  # pragma: allowlist secret
Revises: 61e2f3f2fca3
Create Date: 2026-06-10 22:51:19.186843

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '94f4bab68a73'  # pragma: allowlist secret
down_revision: Union[str, Sequence[str], None] = '61e2f3f2fca3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
