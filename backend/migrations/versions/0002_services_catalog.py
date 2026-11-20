"""Add tenant-scoped service catalogue and station pricing."""
from alembic import op
import sqlalchemy as sa
revision="0002_services"
down_revision="0001_initial"
branch_labels=None
depends_on=None
def upgrade():
    op.create_table("services",
        sa.Column("id",sa.Integer(),primary_key=True),
        sa.Column("company_id",sa.Integer(),sa.ForeignKey("companies.id",ondelete="CASCADE"),nullable=False),
        sa.Column("station_id",sa.Integer(),sa.ForeignKey("stations.id",ondelete="CASCADE"),nullable=True),
        sa.Column("code",sa.String(40),nullable=False),
        sa.Column("name",sa.String(160),nullable=False),
        sa.Column("description",sa.String(500)),
        sa.Column("category",sa.String(60),nullable=False,server_default="lavage"),
        sa.Column("price",sa.Integer(),nullable=False),
        sa.Column("duration_minutes",sa.Integer()),
        sa.Column("is_active",sa.Boolean(),nullable=False,server_default=sa.true()),
        sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now()),
        sa.UniqueConstraint("company_id","station_id","code",name="uq_service_scope_code"))
    op.create_index("ix_services_company_id","services",["company_id"])
    op.create_index("ix_services_station_id","services",["station_id"])
def downgrade():
    op.drop_index("ix_services_station_id",table_name="services")
    op.drop_index("ix_services_company_id",table_name="services")
    op.drop_table("services")
