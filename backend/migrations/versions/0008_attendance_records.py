"""Add daily attendance, absence, leave and overtime records."""
from alembic import op
import sqlalchemy as sa
revision="0008_attendance_records"
down_revision="0007_personnel_payroll"
branch_labels=None
depends_on=None
def upgrade():
    op.create_table("attendance_records",
      sa.Column("id",sa.Integer(),primary_key=True),
      sa.Column("company_id",sa.Integer(),sa.ForeignKey("companies.id",ondelete="CASCADE"),nullable=False),
      sa.Column("station_id",sa.Integer(),sa.ForeignKey("stations.id"),nullable=False),
      sa.Column("employee_id",sa.Integer(),sa.ForeignKey("employees.id",ondelete="RESTRICT"),nullable=False),
      sa.Column("created_by",sa.Integer(),sa.ForeignKey("users.id"),nullable=False),
      sa.Column("work_date",sa.Date(),nullable=False),
      sa.Column("status",sa.String(20),nullable=False),
      sa.Column("regular_hours",sa.Integer(),nullable=False,server_default="0"),
      sa.Column("overtime_hours",sa.Integer(),nullable=False,server_default="0"),
      sa.Column("late_minutes",sa.Integer(),nullable=False,server_default="0"),
      sa.Column("leave_type",sa.String(30)),sa.Column("note",sa.String(500)),
      sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now()),
      sa.UniqueConstraint("company_id","employee_id","work_date",name="uq_attendance_employee_day"))
    for col in ("company_id","station_id","employee_id","work_date"):
      op.create_index(f"ix_attendance_records_{col}","attendance_records",[col])
def downgrade():
    for col in ("company_id","station_id","employee_id","work_date"):
      op.drop_index(f"ix_attendance_records_{col}",table_name="attendance_records")
    op.drop_table("attendance_records")
