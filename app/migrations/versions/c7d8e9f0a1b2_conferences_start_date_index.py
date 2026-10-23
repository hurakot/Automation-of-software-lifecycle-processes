"""Индекс по дате начала конференции

Revision ID: c7d8e9f0a1b2
Revises: b3f1c2d4e5a6
"""
from alembic import op

revision = 'c7d8e9f0a1b2'
down_revision = 'b3f1c2d4e5a6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_index('ix_conferences_start_date', 'conferences', ['start_date'])


def downgrade():
    op.drop_index('ix_conferences_start_date', table_name='conferences')
