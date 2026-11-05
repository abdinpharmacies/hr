from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0001_delivery'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('delivery',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('source', sa.String(256), nullable=False),
        sa.Column('event_id', sa.String(256), nullable=False),
        sa.Column('kind', sa.String(24), nullable=False),
        sa.Column('payload', postgresql.JSONB(), nullable=False),
        sa.Column('digest', sa.String(64), nullable=False),
        sa.Column('state', sa.String(24), nullable=False),
        sa.Column('attempts', sa.Integer(), nullable=False),
        sa.Column('next_attempt', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_success', sa.DateTime(timezone=True)),
        sa.Column('error', sa.String(256)),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('source', 'event_id'))
    op.create_index('ix_delivery_state', 'delivery', ['state'])


def downgrade():
    raise RuntimeError('Delivery history must be retained; restore a verified backup instead.')
