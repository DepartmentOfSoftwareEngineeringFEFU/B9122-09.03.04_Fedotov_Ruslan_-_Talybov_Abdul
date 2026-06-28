"""Compatibility revision for existing local Docker volumes.

Revision ID: 20260531_0003
Revises: 20260525_0002
Create Date: 2026-05-31 00:03:00
"""

from typing import Sequence, Union


revision: str = "20260531_0003"
down_revision: Union[str, None] = "20260525_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
