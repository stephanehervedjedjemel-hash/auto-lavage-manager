from pydantic import BaseModel, ConfigDict, Field
from typing import Literal
class TicketLineCreate(BaseModel):
    service_id:int=Field(gt=0)
    quantity:int=Field(ge=1,le=50)
class TicketCreate(BaseModel):
    station_id:int=Field(gt=0)
    customer_name:str|None=Field(default=None,max_length=160)
    customer_phone:str|None=Field(default=None,max_length=40)
    vehicle_type:str=Field(min_length=2,max_length=60)
    vehicle_registration:str|None=Field(default=None,max_length=30)
    lines:list[TicketLineCreate]=Field(min_length=1,max_length=30)
class PaymentCreate(BaseModel):
    amount:int=Field(gt=0,le=2_000_000_000)
    method:Literal["cash","wave","orange_money","mtn_money","moov_money","card","other"]
    reference:str|None=Field(default=None,max_length=100)
class TicketLineRead(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    id:int
    service_id:int
    service_code:str
    service_name:str
    quantity:int
    unit_price:int
    line_total:int
class PaymentRead(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    id:int
    amount:int
    method:str
    reference:str|None
    created_at:object
class TicketRead(BaseModel):
    id:int
    company_id:int
    station_id:int
    ticket_number:str
    customer_name:str|None
    customer_phone:str|None
    vehicle_type:str
    vehicle_registration:str|None
    subtotal:int
    discount:int
    total:int
    paid_amount:int
    remaining_amount:int
    status:str
    created_at:object
    lines:list[TicketLineRead]
    payments:list[PaymentRead]
