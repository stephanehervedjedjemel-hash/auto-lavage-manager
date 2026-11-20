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
