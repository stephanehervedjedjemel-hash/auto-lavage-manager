"""Add employee attribution and commission ledger.

Works both on a fresh database and on development databases previously created
with SQLAlchemy create_all(). Existing tables are left intact.
"""
from alembic import op
import sqlalchemy as sa
revision = "20261120_commissions"
down_revision = "0010_inventory"
branch_labels = None
depends_on = None

def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("ticket_lines"):
        columns = {c["name"] for c in inspector.get_columns("ticket_lines")}
        if "employee_id" not in columns:
            with op.batch_alter_table("ticket_lines") as batch:
                batch.add_column(sa.Column("employee_id", sa.Integer(), nullable=True))
                batch.create_index("ix_ticket_lines_employee_id", ["employee_id"])
                batch.create_foreign_key(
                    "fk_ticket_lines_employee_id_employees",
                    "employees", ["employee_id"], ["id"], ondelete="RESTRICT"
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
            with op.batch_alter_table("ticket_lines") as batch:
                if "ix_ticket_lines_employee_id" in indexes:
                    batch.drop_index("ix_ticket_lines_employee_id")
                batch.drop_column("employee_id")
