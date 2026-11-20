from datetime import date
from app.models import CommissionRule

def test_commission_rule_model_supports_fixed_and_percentage_rules():
    fixed = CommissionRule(company_id=1, code="FIXE", name="Commission fixe",
        calculation_type="fixed", value=250, effective_from=date(2026, 1, 1), created_by=1)
    percent = CommissionRule(company_id=1, code="PCT", name="Commission 10 pour cent",
        calculation_type="percent", value=1000, effective_from=date(2026, 1, 1), created_by=1)
    assert fixed.value == 250
    assert percent.value == 1000
