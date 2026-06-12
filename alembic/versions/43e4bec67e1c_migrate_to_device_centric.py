"""migrate_to_device_centric

Revision ID: 43e4bec67e1c
Revises: cd4fef5214a5
Create Date: 2026-06-12 17:15:47.822764

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '43e4bec67e1c'
down_revision: Union[str, Sequence[str], None] = 'cd4fef5214a5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add new columns to devices
    op.add_column('devices', sa.Column('token_balance', sa.Integer(), server_default='0', nullable=False))
    op.add_column('devices', sa.Column('active', sa.Boolean(), server_default='true', nullable=False))

    # 2. Add device_id to transactions and link it
    op.add_column('mpesa_transactions', sa.Column('device_id', sa.String(), nullable=True))

    # 3. Drop the old license table
    op.drop_table('licenses')

    # 4. Drop the old license_id column from devices
    op.drop_column('devices', 'license_id')
