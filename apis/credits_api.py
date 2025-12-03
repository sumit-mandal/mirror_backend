from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session 
from databases.database_connection import get_db 
from databases.table_details import Credit, User, Company 
from schemas.schemas import CreditCreate, CreditRead, CreditClaimRequest, CreditClaimResponse
from uuid import UUID
from datetime import datetime, timezone
import secrets
import string

router = APIRouter(prefix="/credits", tags=["credits"])

def generate_credit_code(length: int = 8):
    """Generate a random alphanumeric code with MIRROR- prefix"""
    alphabet = string.ascii_uppercase + string.digits
    random_part = ''.join(secrets.choice(alphabet) for _ in range(length))
    return f"MIRROR-{random_part}"

@router.post("/create",response_model=CreditRead, status_code=status.HTTP_201_CREATED)
def create_credit(
    payload: CreditCreate,
    company_id: UUID,
    created_by_user_id: UUID,
    db: Session = Depends(get_db)
):
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    # verify that user exists and is associated with the company
    user = db.query(User).filter(
        User.id == created_by_user_id,
        User.company_id == company_id
    ).first()
    if not user:
        raise HTTPException(
            status_code=403,
            detail="User not found or does not belong to this company"
        )

    # Generate code if not provided, otherwise validate it starts with MIRROR-
    if payload.code:
        code = payload.code.upper().strip()
        
    else:
        # Generate code with MIRROR- prefix
        code = generate_credit_code()
        # Ensure uniqueness by checking and regenerating if needed
        max_attempts = 10
        attempts = 0
        while db.query(Credit).filter(Credit.code == code).first() and attempts < max_attempts:
            code = generate_credit_code()
            attempts += 1
        
        if attempts >= max_attempts:
            raise HTTPException(
                status_code=500,
                detail="Failed to generate unique credit code. Please try again."
            )

    # Check if code already exists 
    existing = db.query(Credit).filter(Credit.code == code).first() 
    if existing: 
        raise HTTPException(status_code=409, detail="Credit code already exists") 

    # Check expiration
    if payload.expires_at and payload.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Expiration date cannot be in the past")

    new_credit = Credit(
        code=code,
        company_id=company_id,
        created_by_user_id=created_by_user_id,
        uses_total=payload.uses_total,
        uses_remaining=payload.uses_total,
        expires_at=payload.expires_at,
        status="active"
    )

    db.add(new_credit)
    db.commit()
    db.refresh(new_credit)
    return new_credit  


@router.post("/claim",response_model=CreditClaimResponse, status_code=status.HTTP_200_OK)
def claim_credit(
    payload: CreditClaimRequest,
    user_id: UUID,
    db: Session = Depends(get_db)
):    
    credit = db.query(Credit).filter(Credit.code == payload.code.upper().strip()).first()
    if not credit:
        return CreditClaimResponse(success=False, message="credit code not found")
    
    # Verify user exists 
    user = db.query(User).filter(User.id == user_id).first()
    if not user: 
        raise HTTPException(status_code=404, detail="User not found")

    #Check if credit is active 
    if credit.status != "active":
        raise HTTPException(status_code=400, detail=f"Credit code is {credit.status}")

    # Check if expired
    if credit.expires_at and credit.expires_at < datetime.now(timezone.utc):
        credit.status = "expired"
        db.commit()
        raise HTTPException(status_code=400, detail="Credit code has expired") 

     # Check if user belongs to the same company
    if user.company_id != credit.company_id:
        raise HTTPException(
            status_code=403,
            detail="You can only claim credits from your own company"
        )

     # Check if already claimed by this user
    if credit.claimed_by_user_id == user_id and credit.uses_remaining == 0:
        raise HTTPException(status_code=400, detail="You have already claimed this credit")

     # Check if uses remaining
    if credit.uses_remaining <= 0:
        credit.status = "claimed"
        db.commit()
        raise HTTPException(status_code=400, detail="Credit code has no uses remaining")

    # Claim the credit
    credit.uses_remaining -= 1
    credit.claimed_by_user_id = user_id
    credit.claimed_at = datetime.now(timezone.utc)
    
    if credit.uses_remaining == 0:
        credit.status = "claimed"

    db.commit()
    db.refresh(credit)

    return CreditClaimResponse(
        success=True,
        message="Credit claimed successfully",
        credit=credit
    )



@router.get("/list/{company_id}", response_model=list[CreditRead])
def list_credits(
    company_id: UUID,
    db: Session = Depends(get_db)
):
    """List all credits for a company"""
    credits = db.query(Credit).filter(
        Credit.company_id == company_id
    ).order_by(Credit.created_at.desc()).all()
    return credits


@router.get("/code/{code}", response_model=CreditRead)
def get_credit_by_code(
    code: str,
    db: Session = Depends(get_db)
):
    """Get credit details by code"""
    credit = db.query(Credit).filter(Credit.code == code.upper().strip()).first()
    if not credit:
        raise HTTPException(status_code=404, detail="Credit not found")
    return credit
    

    