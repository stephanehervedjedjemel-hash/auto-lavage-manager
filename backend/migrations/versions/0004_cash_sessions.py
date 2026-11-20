"""Add cash sessions and manual cash movements."""
from alembic import op
import sqlalchemy as sa
revision="0004_cash"
down_revision="0003_tickets"
branch_labels=None
depends_on=None
def upgrade():
    op.create_table("cash_sessions",
      sa.Column("id",sa.Integer(),primary_key=True),
      sa.Column("company_id",sa.Integer(),sa.ForeignKey("companies.id",ondelete="CASCADE"),nullable=False),
      sa.Column("station_id",sa.Integer(),sa.ForeignKey("stations.id"),nullable=False),
      sa.Column("opened_by",sa.Integer(),sa.ForeignKey("users.id"),nullable=False),
      sa.Column("closed_by",sa.Integer(),sa.ForeignKey("users.id")),
      sa.Column("opening_amount",sa.Integer(),nullable=False),
      sa.Column("closing_amount",sa.Integer()),sa.Column("expected_amount",sa.Integer()),sa.Column("difference",sa.Integer()),
      sa.Column("status",sa.String(20),nullable=False,server_default="open"),
      sa.Column("opened_at",sa.DateTime(timezone=True),server_default=sa.func.now()),
      sa.Column("closed_at",sa.DateTime(timezone=True)))
    for col in ("company_id","station_id"): op.create_index(f"ix_cash_sessions_{col}","cash_sessions",[col])
    op.create_table("cash_movements",
      sa.Column("id",sa.Integer(),primary_key=True),
      sa.Column("company_id",sa.Integer(),sa.ForeignKey("companies.id",ondelete="CASCADE"),nullable=False),
      sa.Column("station_id",sa.Integer(),sa.ForeignKey("stations.id"),nullable=False),
      sa.Column("session_id",sa.Integer(),sa.ForeignKey("cash_sessions.id",ondelete="RESTRICT"),nullable=False),
      sa.Column("created_by",sa.Integer(),sa.ForeignKey("users.id"),nullable=False),
      sa.Column("direction",sa.String(10),nullable=False),sa.Column("amount",sa.Integer(),nullable=False),
      sa.Column("reason",sa.String(180),nullable=False),
      sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now()))
    for col in ("company_id","station_id","session_id"): op.create_index(f"ix_cash_movements_{col}","cash_movements",[col])
def downgrade():
    for col in ("company_id","station_id","session_id"): op.drop_index(f"ix_cash_movements_{col}",table_name="cash_movements")
    op.drop_table("cash_movements")
    for col in ("company_id","station_id"): op.drop_index(f"ix_cash_sessions_{col}",table_name="cash_sessions")
    op.drop_table("cash_sessions")
