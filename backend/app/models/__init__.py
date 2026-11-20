from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db import Base
class Company(Base):
    __tablename__="companies"
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    legal_name: Mapped[str]=mapped_column(String(180),nullable=False)
    display_name: Mapped[str]=mapped_column(String(180),nullable=False)
    email: Mapped[str|None]=mapped_column(String(255),unique=True)
    phone: Mapped[str|None]=mapped_column(String(40))
    currency: Mapped[str]=mapped_column(String(3),default="XOF",nullable=False)
    is_active: Mapped[bool]=mapped_column(Boolean,default=True,nullable=False)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())
    stations: Mapped[list["Station"]]=relationship(back_populates="company",cascade="all, delete-orphan")
    users: Mapped[list["User"]]=relationship(back_populates="company",cascade="all, delete-orphan")
class Station(Base):
    __tablename__="stations"
    __table_args__=(UniqueConstraint("company_id","code",name="uq_station_company_code"),)
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    company_id: Mapped[int]=mapped_column(ForeignKey("companies.id",ondelete="CASCADE"),index=True)
    name: Mapped[str]=mapped_column(String(160),nullable=False)
    code: Mapped[str]=mapped_column(String(40),nullable=False)
    address: Mapped[str|None]=mapped_column(String(255))
    city: Mapped[str|None]=mapped_column(String(100))
    is_active: Mapped[bool]=mapped_column(Boolean,default=True,nullable=False)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())
    company: Mapped[Company]=relationship(back_populates="stations")
class User(Base):
    __tablename__="users"
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    company_id: Mapped[int]=mapped_column(ForeignKey("companies.id",ondelete="CASCADE"),index=True)
    station_id: Mapped[int|None]=mapped_column(ForeignKey("stations.id",ondelete="SET NULL"),nullable=True)
    full_name: Mapped[str]=mapped_column(String(180),nullable=False)
    email: Mapped[str]=mapped_column(String(255),unique=True,index=True,nullable=False)
    password_hash: Mapped[str]=mapped_column(String(255),nullable=False)
    role: Mapped[str]=mapped_column(String(30),default="company_admin",nullable=False)
    is_active: Mapped[bool]=mapped_column(Boolean,default=True,nullable=False)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())
    company: Mapped[Company]=relationship(back_populates="users")
class Service(Base):
    __tablename__="services"
    __table_args__=(UniqueConstraint("company_id","station_id","code",name="uq_service_scope_code"),)
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    company_id: Mapped[int]=mapped_column(ForeignKey("companies.id",ondelete="CASCADE"),index=True,nullable=False)
    station_id: Mapped[int|None]=mapped_column(ForeignKey("stations.id",ondelete="CASCADE"),index=True,nullable=True)
    code: Mapped[str]=mapped_column(String(40),nullable=False)
    name: Mapped[str]=mapped_column(String(160),nullable=False)
    description: Mapped[str|None]=mapped_column(String(500))
    category: Mapped[str]=mapped_column(String(60),default="lavage",nullable=False)
    price: Mapped[int]=mapped_column(Integer,nullable=False)
    duration_minutes: Mapped[int|None]=mapped_column(Integer)
    is_active: Mapped[bool]=mapped_column(Boolean,default=True,nullable=False)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())

class Ticket(Base):
    __tablename__="tickets"
    __table_args__=(UniqueConstraint("company_id","ticket_number",name="uq_ticket_company_number"),)
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    company_id: Mapped[int]=mapped_column(ForeignKey("companies.id",ondelete="CASCADE"),index=True,nullable=False)
    station_id: Mapped[int]=mapped_column(ForeignKey("stations.id"),index=True,nullable=False)
    ticket_number: Mapped[str]=mapped_column(String(50),nullable=False)
    customer_name: Mapped[str|None]=mapped_column(String(160))
    customer_phone: Mapped[str|None]=mapped_column(String(40))
    vehicle_type: Mapped[str]=mapped_column(String(60),nullable=False)
    vehicle_registration: Mapped[str|None]=mapped_column(String(30))
    subtotal: Mapped[int]=mapped_column(Integer,nullable=False)
    discount: Mapped[int]=mapped_column(Integer,default=0,nullable=False)
    total: Mapped[int]=mapped_column(Integer,nullable=False)
    status: Mapped[str]=mapped_column(String(20),default="unpaid",nullable=False)
    created_by: Mapped[int]=mapped_column(ForeignKey("users.id"),nullable=False)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())
class TicketLine(Base):
    __tablename__="ticket_lines"
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    ticket_id: Mapped[int]=mapped_column(ForeignKey("tickets.id",ondelete="CASCADE"),index=True,nullable=False)
    service_id: Mapped[int]=mapped_column(ForeignKey("services.id"),nullable=False)
    service_code: Mapped[str]=mapped_column(String(40),nullable=False)
    service_name: Mapped[str]=mapped_column(String(160),nullable=False)
    quantity: Mapped[int]=mapped_column(Integer,nullable=False)
    unit_price: Mapped[int]=mapped_column(Integer,nullable=False)
    line_total: Mapped[int]=mapped_column(Integer,nullable=False)
class Payment(Base):
    __tablename__="payments"
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    ticket_id: Mapped[int]=mapped_column(ForeignKey("tickets.id",ondelete="RESTRICT"),index=True,nullable=False)
    company_id: Mapped[int]=mapped_column(ForeignKey("companies.id",ondelete="CASCADE"),index=True,nullable=False)
    station_id: Mapped[int]=mapped_column(ForeignKey("stations.id"),index=True,nullable=False)
    amount: Mapped[int]=mapped_column(Integer,nullable=False)
    method: Mapped[str]=mapped_column(String(30),nullable=False)
    reference: Mapped[str|None]=mapped_column(String(100))
    received_by: Mapped[int]=mapped_column(ForeignKey("users.id"),nullable=False)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())


class CashSession(Base):
    __tablename__="cash_sessions"
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    company_id: Mapped[int]=mapped_column(ForeignKey("companies.id",ondelete="CASCADE"),index=True,nullable=False)
    station_id: Mapped[int]=mapped_column(ForeignKey("stations.id"),index=True,nullable=False)
    opened_by: Mapped[int]=mapped_column(ForeignKey("users.id"),nullable=False)
    closed_by: Mapped[int|None]=mapped_column(ForeignKey("users.id"),nullable=True)
    opening_amount: Mapped[int]=mapped_column(Integer,nullable=False)
    closing_amount: Mapped[int|None]=mapped_column(Integer,nullable=True)
    expected_amount: Mapped[int|None]=mapped_column(Integer,nullable=True)
    difference: Mapped[int|None]=mapped_column(Integer,nullable=True)
    status: Mapped[str]=mapped_column(String(20),default="open",nullable=False)
    opened_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())
    closed_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)

class CashMovement(Base):
    __tablename__="cash_movements"
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    company_id: Mapped[int]=mapped_column(ForeignKey("companies.id",ondelete="CASCADE"),index=True,nullable=False)
    station_id: Mapped[int]=mapped_column(ForeignKey("stations.id"),index=True,nullable=False)
    session_id: Mapped[int]=mapped_column(ForeignKey("cash_sessions.id",ondelete="RESTRICT"),index=True,nullable=False)
    created_by: Mapped[int]=mapped_column(ForeignKey("users.id"),nullable=False)
    direction: Mapped[str]=mapped_column(String(10),nullable=False)
    amount: Mapped[int]=mapped_column(Integer,nullable=False)
    reason: Mapped[str]=mapped_column(String(180),nullable=False)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())


from datetime import date

class Expense(Base):
    __tablename__="expenses"
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    company_id: Mapped[int]=mapped_column(ForeignKey("companies.id",ondelete="CASCADE"),index=True,nullable=False)
    station_id: Mapped[int]=mapped_column(ForeignKey("stations.id"),index=True,nullable=False)
    created_by: Mapped[int]=mapped_column(ForeignKey("users.id"),nullable=False)
    category: Mapped[str]=mapped_column(String(40),nullable=False)
    label: Mapped[str]=mapped_column(String(180),nullable=False)
    vendor: Mapped[str|None]=mapped_column(String(160))
    description: Mapped[str|None]=mapped_column(String(500))
    expense_date: Mapped[date]=mapped_column(Date,nullable=False,index=True)
    amount: Mapped[int]=mapped_column(Integer,nullable=False)
    receipt_name: Mapped[str|None]=mapped_column(String(255))
    receipt_url: Mapped[str|None]=mapped_column(String(500))
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())

class ExpensePayment(Base):
    __tablename__="expense_payments"
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    expense_id: Mapped[int]=mapped_column(ForeignKey("expenses.id",ondelete="RESTRICT"),index=True,nullable=False)
    company_id: Mapped[int]=mapped_column(ForeignKey("companies.id",ondelete="CASCADE"),index=True,nullable=False)
    station_id: Mapped[int]=mapped_column(ForeignKey("stations.id"),index=True,nullable=False)
    paid_by: Mapped[int]=mapped_column(ForeignKey("users.id"),nullable=False)
    amount: Mapped[int]=mapped_column(Integer,nullable=False)
    method: Mapped[str]=mapped_column(String(30),nullable=False)
    reference: Mapped[str|None]=mapped_column(String(100))
    paid_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())
