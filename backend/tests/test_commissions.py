from datetime import date, datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.db import Base
from app.commissioning import accrue_commission
from app.models import Company, CommissionEntry, CommissionRule, Employee, Service, Station, Ticket, TicketLine, User

def _session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)(), engine

def _fixture(db, rule_type="percent", rule_value=1000):
    company = Company(legal_name="Lavage Test", display_name="Lavage Test", currency="XOF")
    db.add(company); db.flush()
    station = Station(company_id=company.id, name="Station 1", code="ST1")
    db.add(station); db.flush()
    user = User(company_id=company.id, station_id=station.id, full_name="Admin",
        email="admin@test.invalid", password_hash="not-a-real-password", role="company_admin")
    db.add(user); db.flush()
    employee = Employee(company_id=company.id, station_id=station.id, created_by=user.id,
        employee_number="LAV-001", full_name="Laveur Test", job_title="Laveur",
        hire_date=date(2026, 1, 1), base_salary=0)
    service = Service(company_id=company.id, station_id=station.id, code="COMPLET",
        name="Lavage complet", price=10000)
    db.add_all([employee, service]); db.flush()
    ticket = Ticket(company_id=company.id, station_id=station.id, ticket_number="T-001",
        vehicle_type="Berline", subtotal=20000, discount=0, total=20000,
        status="unpaid", created_by=user.id, created_at=datetime.now(timezone.utc))
    db.add(ticket); db.flush()
    line = TicketLine(ticket_id=ticket.id, service_id=service.id, employee_id=employee.id,
        service_code=service.code, service_name=service.name, quantity=2,
        unit_price=10000, line_total=20000)
    rule = CommissionRule(company_id=company.id, station_id=station.id, employee_id=employee.id,
        service_id=service.id, code="REGLE-1", name="Commission test",
        calculation_type=rule_type, value=rule_value, effective_from=date(2026, 1, 1),
        created_by=user.id)
    db.add_all([line, rule]); db.flush()
    return ticket, line, employee, rule

def test_percentage_commission_is_snapshotted_on_ticket_line():
    db, engine = _session()
    try:
        ticket, line, employee, rule = _fixture(db)
        entry = accrue_commission(db, ticket, line, employee.id)
        db.commit()
        assert entry.amount == 2000  # 10% of 20,000 FCFA
        rule.value = 2000
        db.commit()
        stored = db.query(CommissionEntry).one()
        assert stored.amount == 2000  # later rule changes do not rewrite the accrual
        assert stored.rule_value == 1000
    finally:
        db.close(); engine.dispose()

def test_fixed_commission_is_applied_per_washed_service_quantity():
    db, engine = _session()
    try:
        ticket, line, employee, rule = _fixture(db, rule_type="fixed", rule_value=250)
        entry = accrue_commission(db, ticket, line, employee.id)
        db.commit()
        assert entry.amount == 500  # 250 FCFA x 2 units
    finally:
        db.close(); engine.dispose()
