"""Формат проведения конференции (очно / онлайн / смешанный)

Revision ID: b3f1c2d4e5a6
Revises: 7d643ecb0fe6
Create Date: 2026-10-24 12:00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b3f1c2d4e5a6'
down_revision = '7d643ecb0fe6'
branch_labels = None
depends_on = None


def upgrade():
    # Новое поле с значением по умолчанию: старые строки получат 'offline',
    # старая версия приложения продолжит работать (поле ей просто не нужно).
    op.add_column('conferences',
                  sa.Column('format', sa.Text(), server_default='offline', nullable=False))


def downgrade():
    op.drop_column('conferences', 'format')
