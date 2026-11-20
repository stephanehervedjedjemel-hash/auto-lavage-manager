"""Add supplier-specific product pricing and station stock movements."""
from alembic import op
import sqlalchemy as sa
revision="0010_inventory"
down_revision="0009_salary_advances"
branch_labels=None
depends_on=None
def upgrade():
    op.create_table("suppliers",sa.Column("id",sa.Integer(),primary_key=True),
      sa.Column("company_id",sa.Integer(),sa.ForeignKey("companies.id",ondelete="CASCADE"),nullable=False),
      sa.Column("name",sa.String(180),nullable=False),sa.Column("phone",sa.String(40)),
      sa.Column("email",sa.String(255)),sa.Column("address",sa.String(255)),
      sa.Column("is_active",sa.Boolean(),nullable=False,server_default=sa.true()),
      sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now()),
      sa.UniqueConstraint("company_id","name",name="uq_supplier_company_name"))
    op.create_index("ix_suppliers_company_id","suppliers",["company_id"])
    op.create_table("inventory_products",sa.Column("id",sa.Integer(),primary_key=True),
      sa.Column("company_id",sa.Integer(),sa.ForeignKey("companies.id",ondelete="CASCADE"),nullable=False),
      sa.Column("sku",sa.String(60),nullable=False),sa.Column("name",sa.String(180),nullable=False),
      sa.Column("category",sa.String(60),nullable=False),sa.Column("unit",sa.String(20),nullable=False,server_default="unite"),
      sa.Column("minimum_stock",sa.Integer(),nullable=False,server_default="0"),
      sa.Column("is_active",sa.Boolean(),nullable=False,server_default=sa.true()),
      sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now()),
      sa.UniqueConstraint("company_id","sku",name="uq_inventory_product_company_sku"))
    op.create_index("ix_inventory_products_company_id","inventory_products",["company_id"])
    op.create_table("supplier_product_prices",sa.Column("id",sa.Integer(),primary_key=True),
      sa.Column("company_id",sa.Integer(),sa.ForeignKey("companies.id",ondelete="CASCADE"),nullable=False),
      sa.Column("supplier_id",sa.Integer(),sa.ForeignKey("suppliers.id",ondelete="RESTRICT"),nullable=False),
      sa.Column("product_id",sa.Integer(),sa.ForeignKey("inventory_products.id",ondelete="RESTRICT"),nullable=False),
      sa.Column("purchase_price",sa.Integer(),nullable=False),
      sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.func.now()),
      sa.UniqueConstraint("supplier_id","product_id",name="uq_supplier_product_price"))
    for col in ("company_id","supplier_id","product_id"):op.create_index(f"ix_supplier_product_prices_{col}","supplier_product_prices",[col])
    op.create_table("stock_movements",sa.Column("id",sa.Integer(),primary_key=True),
      sa.Column("company_id",sa.Integer(),sa.ForeignKey("companies.id",ondelete="CASCADE"),nullable=False),
      sa.Column("station_id",sa.Integer(),sa.ForeignKey("stations.id"),nullable=False),
      sa.Column("product_id",sa.Integer(),sa.ForeignKey("inventory_products.id",ondelete="RESTRICT"),nullable=False),
      sa.Column("supplier_id",sa.Integer(),sa.ForeignKey("suppliers.id",ondelete="RESTRICT")),
      sa.Column("created_by",sa.Integer(),sa.ForeignKey("users.id"),nullable=False),
      sa.Column("movement_type",sa.String(20),nullable=False),sa.Column("quantity",sa.Integer(),nullable=False),
      sa.Column("unit_cost",sa.Integer(),nullable=False,server_default="0"),
      sa.Column("reference",sa.String(100)),sa.Column("note",sa.String(500)),
      sa.Column("moved_at",sa.DateTime(timezone=True),server_default=sa.func.now()))
    for col in ("company_id","station_id","product_id"):op.create_index(f"ix_stock_movements_{col}","stock_movements",[col])
def downgrade():
    for col in ("company_id","station_id","product_id"):op.drop_index(f"ix_stock_movements_{col}",table_name="stock_movements")
    op.drop_table("stock_movements")
    for col in ("company_id","supplier_id","product_id"):op.drop_index(f"ix_supplier_product_prices_{col}",table_name="supplier_product_prices")
    op.drop_table("supplier_product_prices")
    op.drop_index("ix_inventory_products_company_id",table_name="inventory_products");op.drop_table("inventory_products")
    op.drop_index("ix_suppliers_company_id",table_name="suppliers");op.drop_table("suppliers")
