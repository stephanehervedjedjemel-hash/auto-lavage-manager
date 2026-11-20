"""Create fixed asset register."""
from alembic import op
import sqlalchemy as sa
revision="0006_fixed_assets"
down_revision="0005_expenses"
branch_labels=None
depends_on=None
def upgrade():
 op.create_table("fixed_assets",
  sa.Column("id",sa.Integer(),primary_key=True),
  sa.Column("company_id",sa.Integer(),sa.ForeignKey("companies.id",ondelete="CASCADE"),nullable=False),
  sa.Column("station_id",sa.Integer(),sa.ForeignKey("stations.id"),nullable=False),
  sa.Column("created_by",sa.Integer(),sa.ForeignKey("users.id"),nullable=False),
  sa.Column("asset_code",sa.String(50),nullable=False),sa.Column("name",sa.String(180),nullable=False),
  sa.Column("category",sa.String(60),nullable=False),sa.Column("description",sa.String(500)),
  sa.Column("supplier",sa.String(160)),sa.Column("acquisition_date",sa.Date(),nullable=False),
  sa.Column("in_service_date",sa.Date(),nullable=False),sa.Column("acquisition_cost",sa.Integer(),nullable=False),
  sa.Column("residual_value",sa.Integer(),nullable=False,server_default="0"),
  sa.Column("useful_life_months",sa.Integer(),nullable=False),
  sa.Column("depreciation_method",sa.String(30),nullable=False,server_default="straight_line"),
  sa.Column("status",sa.String(20),nullable=False,server_default="active"),
  sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now()),
  sa.UniqueConstraint("company_id","asset_code",name="uq_asset_company_code"))
 for col in ("company_id","station_id"):op.create_index(f"ix_fixed_assets_{col}","fixed_assets",[col])
def downgrade():
 for col in ("company_id","station_id"):op.drop_index(f"ix_fixed_assets_{col}",table_name="fixed_assets")
 op.drop_table("fixed_assets")
