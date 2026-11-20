"""Add employee register and controlled payroll periods."""
from alembic import op
import sqlalchemy as sa
revision="0007_personnel_payroll"
down_revision="0006_fixed_assets"
branch_labels=None
depends_on=None
def upgrade():
    op.create_table("employees",
      sa.Column("id",sa.Integer(),primary_key=True),
      sa.Column("company_id",sa.Integer(),sa.ForeignKey("companies.id",ondelete="CASCADE"),nullable=False),
      sa.Column("station_id",sa.Integer(),sa.ForeignKey("stations.id"),nullable=False),
      sa.Column("created_by",sa.Integer(),sa.ForeignKey("users.id"),nullable=False),
      sa.Column("employee_number",sa.String(40),nullable=False),sa.Column("full_name",sa.String(180),nullable=False),
      sa.Column("phone",sa.String(40)),sa.Column("email",sa.String(255)),sa.Column("job_title",sa.String(120),nullable=False),
      sa.Column("contract_type",sa.String(30),nullable=False,server_default="permanent"),
      sa.Column("hire_date",sa.Date(),nullable=False),sa.Column("end_date",sa.Date()),
      sa.Column("salary_basis",sa.String(20),nullable=False,server_default="monthly"),
      sa.Column("base_salary",sa.Integer(),nullable=False),sa.Column("is_active",sa.Boolean(),nullable=False,server_default=sa.true()),
      sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now()),
      sa.UniqueConstraint("company_id","employee_number",name="uq_employee_company_number"))
    for col in ("company_id","station_id"):op.create_index(f"ix_employees_{col}","employees",[col])
    op.create_table("payroll_periods",
      sa.Column("id",sa.Integer(),primary_key=True),sa.Column("company_id",sa.Integer(),sa.ForeignKey("companies.id",ondelete="CASCADE"),nullable=False),
      sa.Column("station_id",sa.Integer(),sa.ForeignKey("stations.id"),nullable=False),
      sa.Column("created_by",sa.Integer(),sa.ForeignKey("users.id"),nullable=False),
      sa.Column("validated_by",sa.Integer(),sa.ForeignKey("users.id")),
      sa.Column("period_type",sa.String(20),nullable=False),sa.Column("start_date",sa.Date(),nullable=False),
      sa.Column("end_date",sa.Date(),nullable=False),sa.Column("status",sa.String(20),nullable=False,server_default="draft"),
      sa.Column("validated_at",sa.DateTime(timezone=True)),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now()))
    for col in ("company_id","station_id","start_date"):op.create_index(f"ix_payroll_periods_{col}","payroll_periods",[col])
    op.create_table("payroll_lines",
      sa.Column("id",sa.Integer(),primary_key=True),sa.Column("payroll_period_id",sa.Integer(),sa.ForeignKey("payroll_periods.id",ondelete="CASCADE"),nullable=False),
      sa.Column("employee_id",sa.Integer(),sa.ForeignKey("employees.id"),nullable=False),
      sa.Column("employee_number",sa.String(40),nullable=False),sa.Column("employee_name",sa.String(180),nullable=False),
      sa.Column("job_title",sa.String(120),nullable=False),sa.Column("base_salary",sa.Integer(),nullable=False),
      sa.Column("bonuses",sa.Integer(),nullable=False,server_default="0"),sa.Column("overtime_pay",sa.Integer(),nullable=False,server_default="0"),
      sa.Column("gross_salary",sa.Integer(),nullable=False),sa.Column("deductions",sa.Integer(),nullable=False,server_default="0"),
      sa.Column("employee_contributions",sa.Integer(),nullable=False,server_default="0"),
      sa.Column("employer_contributions",sa.Integer(),nullable=False,server_default="0"),
      sa.Column("advance_deduction",sa.Integer(),nullable=False,server_default="0"),sa.Column("net_due",sa.Integer(),nullable=False),
      sa.Column("note",sa.String(500)))
    op.create_index("ix_payroll_lines_period","payroll_lines",["payroll_period_id"])
    op.create_index("ix_payroll_lines_employee","payroll_lines",["employee_id"])
    op.create_table("payroll_payments",
      sa.Column("id",sa.Integer(),primary_key=True),sa.Column("payroll_line_id",sa.Integer(),sa.ForeignKey("payroll_lines.id",ondelete="RESTRICT"),nullable=False),
      sa.Column("company_id",sa.Integer(),sa.ForeignKey("companies.id",ondelete="CASCADE"),nullable=False),
      sa.Column("station_id",sa.Integer(),sa.ForeignKey("stations.id"),nullable=False),
      sa.Column("paid_by",sa.Integer(),sa.ForeignKey("users.id"),nullable=False),sa.Column("amount",sa.Integer(),nullable=False),
      sa.Column("method",sa.String(30),nullable=False),sa.Column("reference",sa.String(100)),
      sa.Column("paid_at",sa.DateTime(timezone=True),server_default=sa.func.now()))
    for col in ("payroll_line_id","company_id","station_id"):op.create_index(f"ix_payroll_payments_{col}","payroll_payments",[col])
def downgrade():
    for col in ("payroll_line_id","company_id","station_id"):op.drop_index(f"ix_payroll_payments_{col}",table_name="payroll_payments")
    op.drop_table("payroll_payments")
    op.drop_index("ix_payroll_lines_employee",table_name="payroll_lines")
    op.drop_index("ix_payroll_lines_period",table_name="payroll_lines")
    op.drop_table("payroll_lines")
    for col in ("company_id","station_id","start_date"):op.drop_index(f"ix_payroll_periods_{col}",table_name="payroll_periods")
    op.drop_table("payroll_periods")
    for col in ("company_id","station_id"):op.drop_index(f"ix_employees_{col}",table_name="employees")
    op.drop_table("employees")
