from fastapi import APIRouter, Depends, HTTPException, status, Request, Header
from sqlalchemy.orm import Session 
from sqlalchemy import and_
from stripe.error import StripeError 
from decimal import Decimal
from datetime import datetime
import stripe

from databases.database_connection import get_db
from databases.table_details import Company
from schemas.schemas import (
    StripeCheckoutSessionRequest,
    StripeCheckoutSessionResponse,
    StripeCustomerRequest,
    StripeCustomerResponse,
)
from utils.stripe_payments import StripeGateway, get_publishable_key

router = APIRouter(prefix="/payments",tags=["Payments"])
gateway = StripeGateway() 

PACK_TYPE_MAP = {
    "5-pack": {"total_licenses": 5},
    "10-pack": {"total_licenses": 10},
    "25-pack": {"total_licenses": 25},
    "50-pack": {"total_licenses": 50},
    "100-pack": {"total_licenses": 100},
}

@router.post("/customers",response_model=StripeCustomerResponse,status_code=status.HTTP_201_CREATED)
def create_or_update_customer(payload: StripeCustomerRequest, db: Session = Depends(get_db)): 
    company = db.query(Company).filter(Company.id == payload.company_id).first()
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")

    customer_payload = {
        "email": payload.email.strip().lower(),
        "name": payload.name.strip(),
        "phone": payload.phone,
        "address": {
            "line1": payload.address_line1,
            "line2": payload.address_line2,
            "city": payload.city,
            "state": payload.state,
            "postal_code": payload.postal_code,
            "country": payload.country,
        },
    }

    customer_payload["address"] = {k: v for k, v in customer_payload["address"].items() if v}
    if not customer_payload["address"]:
        customer_payload.pop("address")

    try: 
        if company.stripe_customer_id:
            customer = gateway.update_customer(company.stripe_customer_id, **customer_payload)

        else:
            customer = gateway.create_customer(**customer_payload)
            company.stripe_customer_id = customer.id
            db.commit()
            db.refresh(company)

    except StripeError as exc:
        raise HTTPException(status_code=502, detail=exc.user_message or "Stripe rejected the request") from exc

    return StripeCustomerResponse(
        customer_id=customer.id,
        publishable_key=get_publishable_key(),
    )

@router.post("/checkout-session", response_model=StripeCheckoutSessionResponse, status_code=status.HTTP_201_CREATED)
def create_checkout_session(payload: StripeCheckoutSessionRequest, db: Session = Depends(get_db)):
    company = db.query(Company).filter(Company.id == payload.company_id).first()
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")
    if not company.stripe_customer_id:
        raise HTTPException(status_code=409, detail="Company does not have a Stripe customer yet")

    try:
        session = gateway.create_checkout_session(
            customer_id=company.stripe_customer_id,
            price_id=payload.price_id,
            quantity=payload.quantity,
            success_url=str(payload.success_url),
            cancel_url=str(payload.cancel_url),
            mode=payload.mode,
            metadata=payload.metadata,
        )
    except StripeError as exc:
        raise HTTPException(status_code=502, detail=exc.user_message or "Stripe rejected the request") from exc

    return StripeCheckoutSessionResponse(
        session_id=session.id,
        url=session.url,
        customer_id=company.stripe_customer_id,
    )


@router.post("/webhook")
async def stripe_webhook(request: Request,db: Session = Depends(get_db)):
    payload = await request.body() 
    sig_header = Header(None) 

    if not sig_header: 
        raise HTTPException(status_code=400, detail="Missing Stripe signature") 

    try: 
        event = gateway.construct_webhook_event(payload, sig_header)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid Stripe signature") 


    if event.type == "checkout.session.completed":
        session= event["data"]["object"]
        payment_intent_id = session.get("payment_intent") 

        if not payment_intent_id:
            return {"status":"ok"} 

        transcation = db.query(PaymentTransaction)