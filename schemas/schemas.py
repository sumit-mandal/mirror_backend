from pydantic import BaseModel,EmailStr,constr,Field
from uuid import UUID 
from datetime import datetime 
from typing import Literal
from pydantic import BaseModel,EmailStr,constr,Field,AnyHttpUrl



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


class CompanyCreate(BaseModel):
    name: str = Field(min_length=1,max_length=255)
    slug: str | None = Field(None, max_length=255)
    industry: str | None = Field(None,max_length=100)
    size: Literal["small", "medium", "large", "enterprise"] | None = None
    billing_email: EmailStr 
    stripe_customer_id: str | None = Field(None, max_length=255)
    logo_url: str | None = Field(None, max_length=500)
    website: str | None = Field(None, max_length=500)
    address_line1: str | None = Field(None, max_length=255)
    address_line2: str | None = Field(None, max_length=255)
    city: str | None = Field(None, max_length=100)
    state: str | None = Field(None, max_length=100)
    postal_code: str | None = Field(None, max_length=20)
    country:str | None = Field(None, max_length=255)

class CompanyRead(BaseModel):
    id : UUID
    name: str
    slug: str | None
    industry: str | None
    size: str | None
    billing_email: str
    stripe_customer_id: str | None
    logo_url: str | None
    website: str | None
    address_line1: str | None
    address_line2: str | None
    city: str | None
    state: str | None
    postal_code: str | None
    country: str | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CompanyUpdate(BaseModel):
    name: str = Field(min_length=1,max_length=255)
    slug: str | None = Field(None, max_length=255)
    industry: str | None = Field(None,max_length=100)
    size: Literal["small", "medium", "large", "enterprise"] | None = None
    billing_email: EmailStr
    stripe_customer_id: str | None = Field(None, max_length=255)
    logo_url: str | None = Field(None, max_length=500)
    website: str | None = Field(None, max_length=500)
    address_line1: str | None = Field(None, max_length=255)
    address_line2: str | None = Field(None, max_length=255)
    city: str | None = Field(None, max_length=100)
    state: str | None = Field(None, max_length=100)
    postal_code: str | None = Field(None, max_length=20)
    country:str | None = Field(None, max_length=255)



class StripeCustomerRequest(BaseModel):
    company_id: UUID
    name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    phone: str | None = Field(None, max_length=20)
    address_line1: str | None = Field(None, max_length=255)
    address_line2: str | None = Field(None, max_length=255)
    city: str | None = Field(None, max_length=100)
    state: str | None = Field(None, max_length=100)
    postal_code: str | None = Field(None, max_length=20)
    country:str | None = Field(None, max_length=255)


class StripeCustomerResponse(BaseModel):
    customer_id: str
    publishable_key: str

class StripeCheckoutSessionRequest(BaseModel):
    company_id: UUID
    price_id: constr(min_length=1, max_length=255)
    quantity: int = Field(ge=1, default=1)
    mode: Literal["payment","subscription"] = "subscription"
    success_url: AnyHttpUrl
    cancel_url: AnyHttpUrl
    metadata: dict[str, str] | None = None


class StripeCheckoutSessionResponse(BaseModel):
    session_id: str
    url: AnyHttpUrl
    customer_id: str


class PaymentTransactionRead(BaseModel):
    id: UUID
    company_id: UUID
    user_id: UUID
    transaction_type: str 
    amount: float 
    currency: str  
    status:str 
    stripe_payment_intent_id: str
    license_pack_id: UUID
    created_at: datetime 
    completed_at: datetime 

    class Config:
        from_attributes = True 

        

class LicensePackRead(BaseModel):
    id: UUID 
    company_id: UUID 
    pack_type: str 
    total_licenses: int 
    used_licenses: int 
    available_licenses: int 
    price_paid: float 
    currency: str 
    purchase_date: datetime 
    expiration_date: datetime | None 
    stripe_payment_id: str | None 
    stripe_invoice_id: str | None 
    status: str 
    created_at: datetime 
    updated_at: datetime 

    class Config:
        from_attributes = True 



class PaymentTransactionRead(BaseModel):
    id: UUID
    company_id: UUID | None
    user_id: UUID | None              
    transaction_type: str
    amount: float
    currency: str
    status: str
    stripe_payment_intent_id: str | None
    stripe_charge_id: str | None
    stripe_invoice_id: str | None
    stripe_customer_id: str | None
    license_pack_id: UUID | None
    product_description: str | None
    initiated_at: datetime | None
    completed_at: datetime | None
    failed_at: datetime | None
    refunded_at: datetime | None
    failure_reason: str | None
    refund_reason: str | None
    refund_amount: float | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True