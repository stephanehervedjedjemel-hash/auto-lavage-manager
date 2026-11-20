"""Add employee salary advance requests and repayments."""
from alembic import op
import sqlalchemy as sa
revision="0009_salary_advances"
down_revision="0008_attendance_records"
branch_labels=None
depends_on=None
def upgrade():
    op.create_table("salary_advances",
      sa.Column("id",sa.Integer(),primary_key=True),
      sa.Column("company_id",sa.Integer(),sa.ForeignKey("companies.id",ondelete="CASCADE"),nullable=False),
      sa.Column("station_id",sa.Integer(),sa.ForeignKey("stations.id"),nullable=False),
      sa.Column("employee_id",sa.Integer(),sa.ForeignKey("employees.id",ondelete="RESTRICT"),nullable=False),
      sa.Column("requested_by",sa.Integer(),sa.ForeignKey("users.id"),nullable=False),
      sa.Column("decided_by",sa.Integer(),sa.ForeignKey("users.id")),
      sa.Column("amount",sa.Integer(),nullable=False),sa.Column("reason",sa.String(500),nullable=False),
      sa.Column("status",sa.String(20),nullable=False,server_default="pending"),
      sa.Column("requested_at",sa.DateTime(timezone=True),server_default=sa.func.now()),
      sa.Column("decided_at",sa.DateTime(timezone=True)),sa.Column("decision_note",sa.String(500)))
    for col in ("company_id","station_id","employee_id"):op.create_index(f"ix_salary_advances_{col}","salary_advances",[col])
    op.create_table("advance_repayments",
      sa.Column("id",sa.Integer(),primary_key=True),
      sa.Column("advance_id",sa.Integer(),sa.ForeignKey("salary_advances.id",ondelete="RESTRICT"),nullable=False),
      sa.Column("company_id",sa.Integer(),sa.ForeignKey("companies.id",ondelete="CASCADE"),nullable=False),
      sa.Column("station_id",sa.Integer(),sa.ForeignKey("stations.id"),nullable=False),
      sa.Column("recorded_by",sa.Integer(),sa.ForeignKey("users.id"),nullable=False),
      sa.Column("amount",sa.Integer(),nullable=False),sa.Column("source",sa.String(20),nullable=False,server_default="manual"),
      sa.Column("reference",sa.String(100)),sa.Column("note",sa.String(500)),
      sa.Column("repaid_at",sa.DateTime(timezone=True),server_default=sa.func.now()))
    for col in ("advance_id","company_id","station_id"):op.create_index(f"ix_advance_repayments_{col}","advance_repayments",[col])
def downgrade():
    for col in ("advance_id","company_id","station_id"):op.drop_index(f"ix_advance_repayments_{col}",table_name="advance_repayments")
    op.drop_table("advance_repayments")
    for col in ("company_id","station_id","employee_id"):op.drop_index(f"ix_salary_advances_{col}",table_name="salary_advances")
    op.drop_table("salary_advances")
