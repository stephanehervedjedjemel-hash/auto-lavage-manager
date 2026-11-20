"""Add tickets, immutable service snapshots and payment records."""
from alembic import op
import sqlalchemy as sa
revision="0003_tickets"
down_revision="0002_services"
branch_labels=None
depends_on=None
def upgrade():
    op.create_table("tickets",
        sa.Column("id",sa.Integer(),primary_key=True),
        sa.Column("company_id",sa.Integer(),sa.ForeignKey("companies.id",ondelete="CASCADE"),nullable=False),
        sa.Column("station_id",sa.Integer(),sa.ForeignKey("stations.id"),nullable=False),
        sa.Column("ticket_number",sa.String(50),nullable=False),
        sa.Column("customer_name",sa.String(160)),sa.Column("customer_phone",sa.String(40)),
        sa.Column("vehicle_type",sa.String(60),nullable=False),sa.Column("vehicle_registration",sa.String(30)),
        sa.Column("subtotal",sa.Integer(),nullable=False),sa.Column("discount",sa.Integer(),nullable=False,server_default="0"),
        sa.Column("total",sa.Integer(),nullable=False),sa.Column("status",sa.String(20),nullable=False,server_default="unpaid"),
        sa.Column("created_by",sa.Integer(),sa.ForeignKey("users.id"),nullable=False),
        sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now()),
        sa.UniqueConstraint("company_id","ticket_number",name="uq_ticket_company_number"))
    for name,table in [("company_id","tickets"),("station_id","tickets")]:
        op.create_index(f"ix_{table}_{name}",table,[name])
    op.create_table("ticket_lines",
        sa.Column("id",sa.Integer(),primary_key=True),
        sa.Column("ticket_id",sa.Integer(),sa.ForeignKey("tickets.id",ondelete="CASCADE"),nullable=False),
        sa.Column("service_id",sa.Integer(),sa.ForeignKey("services.id"),nullable=False),
        sa.Column("service_code",sa.String(40),nullable=False),sa.Column("service_name",sa.String(160),nullable=False),
        sa.Column("quantity",sa.Integer(),nullable=False),sa.Column("unit_price",sa.Integer(),nullable=False),
        sa.Column("line_total",sa.Integer(),nullable=False))
    op.create_index("ix_ticket_lines_ticket_id","ticket_lines",["ticket_id"])
    op.create_table("payments",
        sa.Column("id",sa.Integer(),primary_key=True),
        sa.Column("ticket_id",sa.Integer(),sa.ForeignKey("tickets.id",ondelete="RESTRICT"),nullable=False),
        sa.Column("company_id",sa.Integer(),sa.ForeignKey("companies.id",ondelete="CASCADE"),nullable=False),
        sa.Column("station_id",sa.Integer(),sa.ForeignKey("stations.id"),nullable=False),
        sa.Column("amount",sa.Integer(),nullable=False),sa.Column("method",sa.String(30),nullable=False),
        sa.Column("reference",sa.String(100)),sa.Column("received_by",sa.Integer(),sa.ForeignKey("users.id"),nullable=False),
        sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now()))
    for name in ("ticket_id","company_id","station_id"):
        op.create_index(f"ix_payments_{name}","payments",[name])
def downgrade():
    for name in ("ticket_id","company_id","station_id"): op.drop_index(f"ix_payments_{name}",table_name="payments")
    op.drop_table("payments")
    op.drop_index("ix_ticket_lines_ticket_id",table_name="ticket_lines")
    op.drop_table("ticket_lines")
    op.drop_index("ix_tickets_station_id",table_name="tickets")
    op.drop_index("ix_tickets_company_id",table_name="tickets")
    op.drop_table("tickets")
