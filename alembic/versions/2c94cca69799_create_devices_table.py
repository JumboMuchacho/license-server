"""create_devices_table

Revision ID: 2c94cca69799
Revises: 43e4bec67e1c
Create Date: 2026-06-12 18:42:23.657206

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2c94cca69799'
down_revision: Union[str, Sequence[str], None] = '43e4bec67e1c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
