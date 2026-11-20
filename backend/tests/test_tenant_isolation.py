from app.models import Company,Station
from app.db import Base
def test_station_model_has_tenant_foreign_key():
    column=Station.__table__.c.company_id
    assert column.index
    assert any(fk.target_fullname=="companies.id" for fk in column.foreign_keys)
def test_company_has_xof_default():
    assert Company.__table__.c.currency.default.arg=="XOF"
