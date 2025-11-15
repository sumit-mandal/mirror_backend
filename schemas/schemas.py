from pydantic import BaseModel,EmailStr,constr,Field
from uuid import UUID 
from datetime import datetime 
from typing import Literal


class UserCreate(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=8, max_length=255)
    role: Literal["free", "team_member", "manager", "admin"] = "free"
    company_id: UUID | None = None
    department: str | None = Field(None, max_length=255)
    job_title: str | None = Field(None, max_length=255)
    avatar_url: str | None = Field(None, max_length=500)


class UserRead(BaseModel):
    id : UUID
    email: EmailStr
    name: str 
    role: str 
    company_id: UUID | None 
    department: str | None 
    job_title: str | None 
    avatar_url: str | None 
    email_verified: bool | None 
    created_at: datetime 
    updated_at: datetime 

    class Config: 
        from_attributes = True 


class UserUpdate(BaseModel):
    email: EmailStr | None = None 
    name: str | None = Field(None,min_length=1,max_length=255)
    password: str | None = Field(None,min_length=1,max_length=255)
    role: Literal["free", "team_member", "manager", "admin"] | None = None
    company_id: UUID | None = None
    department: str | None = Field(None, max_length=255)
    job_title: str | None = Field(None, max_length=255)
    avatar_url: str | None = Field(None, max_length=500)

class LoginRequest(BaseModel):
    email: EmailStr
    password: str 


class LoginResponse(BaseModel):
    access_token: str 
    token_type: str = "bearer"
    user: UserRead 

