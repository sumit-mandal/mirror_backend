from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from uuid import UUID
from databases.database_connection import get_db
from databases.table_details import Company, User
from schemas.schemas import CompanyCreate, CompanyRead, CompanyUpdate
from utils import identifier
from utils.identifier import get_user_by_identifier


router = APIRouter(prefix="/companies",tags=["Companies"]) 



def get_company_by_identifier(identifier: str, db: Session) -> Company:
    try:
        company_id = UUID(identifier)
        company = db.query(Company).filter(Company.id == company_id).first() 
    
    except ValueError:
        company = db.query(Company).filter(Company.slug == identifier).first()

    return company


@router.post("/create_company",response_model=CompanyRead, status_code=status.HTTP_201_CREATED)
def create_company(payload: CompanyCreate, db: Session = Depends(get_db)):
    if payload.slug:
        if db.query(Company).filter(Company.slug == payload.slug).first():
            raise HTTPException(status_code=409, detail="Slug already exists")
    
    if payload.stripe_customer_id:
         if db.query(Company).filter(Company.stripe_customer_id == payload.stripe_customer_id).first():
            raise HTTPException(status_code=409, detail="Stripe customer ID already exists"
            )

    new_company = Company(
        name=payload.name.strip(),
        slug=payload.slug.strip().lower() if payload.slug else None,
        industry=payload.industry,
        size=payload.size,
        billing_email=payload.billing_email.strip().lower() if payload.billing_email else None,
        stripe_customer_id=payload.stripe_customer_id,
        logo_url=payload.logo_url,
        website=payload.website,
        address_line1=payload.address_line1,
        address_line2=payload.address_line2,
        city=payload.city,
        state=payload.state,
        postal_code=payload.postal_code,
        country=payload.country.upper() if payload.country else None,
    )

    db.add(new_company)
    db.commit()
    db.refresh(new_company)

    return new_company



@router.get("/list_companies",response_model=list[CompanyRead])
def list_companies(db: Session = Depends(get_db)):
    return db.query(Company).order_by(Company.created_at.desc()).all()


@router.get("/search", response_model=list[CompanyRead])
def search_companies(
    email: str | None = Query(None, description="search by user email"),
    user_identifier: str | None = Query(None, description="serach by user ID or email"),
    slug: str | None = Query(None, description="search by company slug"),
    country: str | None = Query(None, decription="search by country"),
    state: str | None = Query(None),
    city: str | None = Query(None),
    db: Session = Depends(get_db)
    ):

    query = db.query(Company)

    if email:
        email_normalized = email.strip().lower()
        user = db.query(User).filter(User.email == email_normalized).first()
        if user and user.company_id:
            query = query.filter(Company.id == user.company_id)
        else:
            return []

    if user_identifier:
        user = get_user_by_identifier(user_identifier, db)
        if user and user.company_id:
            query = query.filter(Company.id == user.company_id)
        else:
            return []


    if slug:
        query = query.filter(Company.slug == slug.strip().lower())

    if country:
        query = query.filter(Company.country == country.upper())

    if state:
        query = query.filter(Company.state.ilike(f"%{state.strip()}%"))

    if city:
        query = query.filter(Company.city.ilike(f"%{city.strip()}%"))

    return query.order_by(Company.created_at.desc()).all()
    

@router.get("/{identifier}",response_model=CompanyRead)
def get_company(identifier: str, db: Session = Depends(get_db)):
    company = get_company_by_identifier(identifier, db)
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


@router.put("/update_company/{identifier}",response_model=CompanyRead)
def update_company(identifier: str, payload: CompanyUpdate, db: Session = Depends(get_db)):
    company = get_company_by_identifier(identifier,db)

    if company is None: 
        raise HTTPException(status_code=404, detail="Company not found")

    if payload.name is not None:
        company.name = payload.name.strip()

    if payload.slug is not None: 
        slug_normalized = payload.slug.strip().lower() 
        existing_company = db.query(Company).fliter(Company.slug==slug_normalized) 

    if payload.industry is not None:
        company.industry = payload.industry

    if payload.size is not None:
        company.size = payload.size

    if payload.billing_email is not None:
        company.billing_email = payload.billing_email.strip().lower()

    if payload.logo_url is not None:
        company.logo_url = payload.logo_url

    if payload.website is not None:
        company.website = payload.website

    if payload.address_line1 is not None:
        company.address_line1 = payload.address_line1

    if payload.address_line2 is not None:
        company.address_line2 = payload.address_line2

    if payload.city is not None:
        company.city = payload.city

    if payload.state is not None:
        company.state = payload.state

    if payload.postal_code is not None:
        company.postal_code = payload.postal_code

    if payload.country is not None:
        company.country = payload.country.upper()


    db.commit()
    db.refresh(company)
    return company

@router.delete("/delete/{identifier}",status_code=status.HTTP_200_OK )
def delete_company(identifier: str, db: Session = Depends(get_db)):
    company = get_company_by_identifier(identifier,db)


@router.get("/company-id-by-email/{email}", response_model=dict)
def get_company_id_by_email(email: str, db: Session = Depends(get_db)):
    email_normalized = email.strip().lower()
    user = db.query(User).filter(User.email == email_normalized).first()
    
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.company_id is None:
        raise HTTPException(status_code=404, detail="User is not associated with any company")
    
    return {"company_id": str(user.company_id)}


@router.get("/by-email/{email}", response_model=CompanyRead)
def get_company_by_email(email: str, db: Session = Depends(get_db)):
    email_normalized = email.strip().lower()
    user = db.query(User).filter(User.email == email_normalized).first()
    
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.company_id is None:
        raise HTTPException(status_code=404, detail="User is not associated with any company")
    
    company = db.query(Company).filter(Company.id == user.company_id).first()
    
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")
    
    return company
