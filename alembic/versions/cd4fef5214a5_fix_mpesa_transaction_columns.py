"""fix mpesa transaction columns

Revision ID: cd4fef5214a5
Revises: e7f87cca05bc
Create Date: 2026-06-11 06:09:59.206417

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cd4fef5214a5'# pragma: allowlist secret
down_revision: Union[str, Sequence[str], None] = 'e7f87cca05bc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
