"""Add employee attribution and commission ledger.

Works both on a fresh database and on development databases previously created
with SQLAlchemy create_all(). Existing tables are left intact.
"""
from alembic import op
import sqlalchemy as sa
revision = "20261120_commissions"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("ticket_lines"):
        columns = {c["name"] for c in inspector.get_columns("ticket_lines")}
        if "employee_id" not in columns:
            op.add_column("ticket_lines", sa.Column("employee_id", sa.Integer(), nullable=True))
            op.create_index("ix_ticket_lines_employee_id", "ticket_lines", ["employee_id"])
            op.create_foreign_key(
                "fk_ticket_lines_employee_id_employees",
                "ticket_lines", "employees", ["employee_id"], ["id"], ondelete="RESTRICT"
            )
    # Create any missing tables from the current metadata, including the commission ledger.
    from app import models  # noqa: F401
    from app.db import Base
    Base.metadata.create_all(bind=bind)

def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for table in ("commission_payments", "commission_entries", "commission_rules"):
        if inspector.has_table(table):
            op.drop_table(table)
    inspector = sa.inspect(bind)
    if inspector.has_table("ticket_lines"):
        columns = {c["name"] for c in inspector.get_columns("ticket_lines")}
        if "employee_id" in columns:
            indexes = {i["name"] for i in inspector.get_indexes("ticket_lines")}
            if "ix_ticket_lines_employee_id" in indexes:
                op.drop_index("ix_ticket_lines_employee_id", table_name="ticket_lines")
            op.drop_column("ticket_lines", "employee_id")
