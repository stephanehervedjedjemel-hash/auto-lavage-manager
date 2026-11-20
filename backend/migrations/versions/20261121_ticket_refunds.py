"""Add immutable ticket refund records."""
from alembic import op
import sqlalchemy as sa

revision = "20261121_ticket_refunds"
down_revision = "20261120_commissions"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("ticket_refunds"):
        op.create_table(
            "ticket_refunds",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("ticket_id", sa.Integer(), sa.ForeignKey("tickets.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("payment_id", sa.Integer(), sa.ForeignKey("payments.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
            sa.Column("station_id", sa.Integer(), sa.ForeignKey("stations.id"), nullable=False),
            sa.Column("amount", sa.Integer(), nullable=False),
            sa.Column("method", sa.String(length=30), nullable=False),
            sa.Column("reference", sa.String(length=100), nullable=True),
            sa.Column("reason", sa.String(length=250), nullable=False),
            sa.Column("refunded_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("refunded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_ticket_refunds_ticket_id", "ticket_refunds", ["ticket_id"])
        op.create_index("ix_ticket_refunds_payment_id", "ticket_refunds", ["payment_id"])
        op.create_index("ix_ticket_refunds_company_id", "ticket_refunds", ["company_id"])
        op.create_index("ix_ticket_refunds_station_id", "ticket_refunds", ["station_id"])


def downgrade():
    bind = op.get_bind()
    if sa.inspect(bind).has_table("ticket_refunds"):
        op.drop_table("ticket_refunds")
