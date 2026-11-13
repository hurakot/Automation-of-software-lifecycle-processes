"""Индекс по дате начала конференции (сортировка на главной странице)

Revision ID: c7d8e9f0a1b2
Revises: b3f1c2d4e5a6
Create Date: 2026-10-25 12:00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'c7d8e9f0a1b2'
down_revision = 'b3f1c2d4e5a6'
branch_labels = None
depends_on = None


def upgrade():
    # CONCURRENTLY строит индекс без блокировки записи в таблицу,
    # но не может выполняться внутри транзакции — отсюда autocommit_block.
    with op.get_context().autocommit_block():
        op.create_index('ix_conferences_start_date', 'conferences', ['start_date'],
                        postgresql_concurrently=True, if_not_exists=True)


def downgrade():
    with op.get_context().autocommit_block():
        op.drop_index('ix_conferences_start_date', table_name='conferences',
                      postgresql_concurrently=True, if_exists=True)
