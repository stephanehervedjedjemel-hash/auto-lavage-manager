"""Add expense commitments and separate expense payments."""
from alembic import op
import sqlalchemy as sa
revision="0005_expenses"
down_revision="0004_cash"
branch_labels=None
depends_on=None
def upgrade():
    op.create_table("expenses",
      sa.Column("id",sa.Integer(),primary_key=True),
      sa.Column("company_id",sa.Integer(),sa.ForeignKey("companies.id",ondelete="CASCADE"),nullable=False),
      sa.Column("station_id",sa.Integer(),sa.ForeignKey("stations.id"),nullable=False),
      sa.Column("created_by",sa.Integer(),sa.ForeignKey("users.id"),nullable=False),
      sa.Column("category",sa.String(40),nullable=False),sa.Column("label",sa.String(180),nullable=False),
      sa.Column("vendor",sa.String(160)),sa.Column("description",sa.String(500)),
      sa.Column("expense_date",sa.Date(),nullable=False),sa.Column("amount",sa.Integer(),nullable=False),
      sa.Column("receipt_name",sa.String(255)),sa.Column("receipt_url",sa.String(500)),
      sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now()))
    for col in ("company_id","station_id","expense_date"): op.create_index(f"ix_expenses_{col}","expenses",[col])
    op.create_table("expense_payments",
      sa.Column("id",sa.Integer(),primary_key=True),
      sa.Column("expense_id",sa.Integer(),sa.ForeignKey("expenses.id",ondelete="RESTRICT"),nullable=False),
      sa.Column("company_id",sa.Integer(),sa.ForeignKey("companies.id",ondelete="CASCADE"),nullable=False),
      sa.Column("station_id",sa.Integer(),sa.ForeignKey("stations.id"),nullable=False),
      sa.Column("paid_by",sa.Integer(),sa.ForeignKey("users.id"),nullable=False),
      sa.Column("amount",sa.Integer(),nullable=False),sa.Column("method",sa.String(30),nullable=False),
      sa.Column("reference",sa.String(100)),sa.Column("paid_at",sa.DateTime(timezone=True),server_default=sa.func.now()))
    for col in ("expense_id","company_id","station_id"): op.create_index(f"ix_expense_payments_{col}","expense_payments",[col])
def downgrade():
    for col in ("expense_id","company_id","station_id"): op.drop_index(f"ix_expense_payments_{col}",table_name="expense_payments")
    op.drop_table("expense_payments")
    for col in ("company_id","station_id","expense_date"): op.drop_index(f"ix_expenses_{col}",table_name="expenses")
    op.drop_table("expenses")
