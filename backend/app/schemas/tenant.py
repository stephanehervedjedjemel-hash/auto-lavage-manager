from pydantic import BaseModel,ConfigDict,Field
class OwnerRegistration(BaseModel):
    bootstrap_secret:str=Field(min_length=12)
    company_legal_name:str=Field(min_length=2,max_length=180)
    company_display_name:str=Field(min_length=2,max_length=180)
    company_email:str|None=None
    company_phone:str|None=None
    station_name:str=Field(min_length=2,max_length=160)
    station_code:str=Field(min_length=2,max_length=40)
    station_address:str|None=None
    station_city:str|None=None
    owner_full_name:str=Field(min_length=2,max_length=180)
    owner_email:str
    password:str=Field(min_length=12,max_length=128)
class LoginInput(BaseModel):
    email:str
    password:str
class StationCreate(BaseModel):
    name:str=Field(min_length=2,max_length=160)
    code:str=Field(min_length=2,max_length=40)
    address:str|None=None
    city:str|None=None
class StationRead(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    id:int
    company_id:int
    name:str
    code:str
    address:str|None
    city:str|None
    is_active:bool
class CompanyRead(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    id:int
    legal_name:str
    display_name:str
    email:str|None
    phone:str|None
    currency:str
    is_active:bool
class TokenRead(BaseModel):
    access_token:str
    token_type:str="bearer"
    company_id:int
    user_id:int
    role:str
