"""add_structured_data_to_documents

Revision ID: 418df9ff6583
Revises: 67179ad993a5
Create Date: 2026-03-03 04:30:10.795651

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '418df9ff6583'
down_revision: Union[str, None] = '67179ad993a5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add structured_data column to store extracted medical information as JSON
    op.add_column('documents', sa.Column('structured_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    # Remove structured_data column
    op.drop_column('documents', 'structured_data')
