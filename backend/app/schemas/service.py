from pydantic import BaseModel, ConfigDict, Field
class ServiceCreate(BaseModel):
    code: str = Field(min_length=2,max_length=40,pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=2,max_length=160)
    description: str|None = Field(default=None,max_length=500)
    category: str = Field(default="lavage",min_length=2,max_length=60)
    price: int = Field(ge=0,le=2_000_000_000)
    duration_minutes: int|None = Field(default=None,ge=1,le=1440)
    station_id: int|None = None
class ServiceUpdate(BaseModel):
    name: str|None = Field(default=None,min_length=2,max_length=160)
    description: str|None = Field(default=None,max_length=500)
    category: str|None = Field(default=None,min_length=2,max_length=60)
    price: int|None = Field(default=None,ge=0,le=2_000_000_000)
    duration_minutes: int|None = Field(default=None,ge=1,le=1440)
    is_active: bool|None = None
class ServiceRead(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    id:int
    company_id:int
    station_id:int|None
    code:str
    name:str
    description:str|None
    category:str
    price:int
    duration_minutes:int|None
    is_active:bool
