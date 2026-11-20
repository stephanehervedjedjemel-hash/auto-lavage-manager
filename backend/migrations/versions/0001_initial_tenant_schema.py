"""Initial tenant, station and user tables."""
from alembic import op
import sqlalchemy as sa
revision="0001_initial"
down_revision=None
branch_labels=None
depends_on=None
def upgrade():
    op.create_table("companies",
      sa.Column("id",sa.Integer(),primary_key=True),
      sa.Column("legal_name",sa.String(180),nullable=False),
      sa.Column("display_name",sa.String(180),nullable=False),
      sa.Column("email",sa.String(255),nullable=True,unique=True),
      sa.Column("phone",sa.String(40)),
      sa.Column("currency",sa.String(3),nullable=False,server_default="XOF"),
      sa.Column("is_active",sa.Boolean(),nullable=False,server_default=sa.true()),
      sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now()))
    op.create_table("stations",
      sa.Column("id",sa.Integer(),primary_key=True),
      sa.Column("company_id",sa.Integer(),sa.ForeignKey("companies.id",ondelete="CASCADE"),nullable=False),
      sa.Column("name",sa.String(160),nullable=False),sa.Column("code",sa.String(40),nullable=False),
      sa.Column("address",sa.String(255)),sa.Column("city",sa.String(100)),
      sa.Column("is_active",sa.Boolean(),nullable=False,server_default=sa.true()),
      sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now()),
      sa.UniqueConstraint("company_id","code",name="uq_station_company_code"))
    op.create_index("ix_stations_company_id","stations",["company_id"])
    op.create_table("users",
      sa.Column("id",sa.Integer(),primary_key=True),
      sa.Column("company_id",sa.Integer(),sa.ForeignKey("companies.id",ondelete="CASCADE"),nullable=False),
      sa.Column("station_id",sa.Integer(),sa.ForeignKey("stations.id",ondelete="SET NULL")),
      sa.Column("full_name",sa.String(180),nullable=False),
      sa.Column("email",sa.String(255),nullable=False,unique=True),
      sa.Column("password_hash",sa.String(255),nullable=False),
      sa.Column("role",sa.String(30),nullable=False,server_default="company_admin"),
      sa.Column("is_active",sa.Boolean(),nullable=False,server_default=sa.true()),
      sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now()))
    op.create_index("ix_users_company_id","users",["company_id"])
    op.create_index("ix_users_email","users",["email"])
def downgrade():
    op.drop_index("ix_users_email",table_name="users")
    op.drop_index("ix_users_company_id",table_name="users")
    op.drop_table("users")
    op.drop_index("ix_stations_company_id",table_name="stations")
    op.drop_table("stations")
    op.drop_table("companies")
