import logging
from fastapi import APIRouter, Depends, HTTPException, status, Request, Header
from sqlalchemy.orm import Session 
from sqlalchemy import and_
from stripe.error import StripeError 
from decimal import Decimal
from datetime import datetime
import stripe
from databases.table_details import Company, PaymentTransaction, LicensePack
from uuid import UUID
from typing import Optional
from schemas.schemas import LicensePackRead, PaymentTransactionRead


from databases.database_connection import get_db
from databases.table_details import Company
from schemas.schemas import (
    StripeCheckoutSessionRequest,
    StripeCheckoutSessionResponse,
    StripeCustomerRequest,
    StripeCustomerResponse,
)
from utils.stripe_payments import StripeGateway, get_publishable_key

logger = logging.getLogger(__name__)

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

        payment_intent_id = session.payment_intent if hasattr(session, 'payment_intent') else None
        amount_total = session.amount_total / 100 if session.amount_total else 0
        currency = session.currency.upper() if session.currency else "USD"
        transaction_type = payload.metadata.get("transaction_type", "license_pack") if payload.metadata else "license_pack"

        if payment_intent_id:
            existing = db.query(PaymentTransaction).filter(
                PaymentTransaction.stripe_payment_intent_id == payment_intent_id
            ).first()
            
            if not existing:
                transaction = PaymentTransaction(
                    company_id=company.id,
                    transaction_type=transaction_type,
                    amount=Decimal(str(amount_total)),
                    currency=currency,
                    status="pending",
                    stripe_payment_intent_id=payment_intent_id,
                    stripe_customer_id=company.stripe_customer_id,
                    product_description=payload.metadata.get("product_description") if payload.metadata else None,
                )
                db.add(transaction)
                db.commit()

    except StripeError as exc:
        raise HTTPException(status_code=502, detail=exc.user_message or "Stripe rejected the request") from exc

    return StripeCheckoutSessionResponse(
        session_id=session.id,
        url=session.url,
        customer_id=company.stripe_customer_id,
    )


@router.post("/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    try:
        # Get raw body for signature verification
        body = await request.body()
        sig_header = request.headers.get("stripe-signature")
        
        # Log incoming request for debugging
        logger.info(f"Webhook received. Headers: {dict(request.headers)}")
        
        # Verify webhook signature
        try:
            if sig_header:
                event = gateway.construct_webhook_event(body, sig_header)
                stripe_event = event
            else:
                # If no signature header, might be from API Gateway - parse JSON directly
                import json
                event_data = json.loads(body.decode('utf-8'))
                # Handle AWS EventBridge format
                stripe_event = event_data.get("detail", event_data)
                # If it's a direct Stripe event, use it as-is
                if "type" not in stripe_event and "data" in event_data:
                    stripe_event = event_data
        except ValueError as e:
            logger.error(f"Webhook signature verification failed: {e}")
            # For debugging, continue without verification - REMOVE IN PRODUCTION
            import json
            event_data = json.loads(body.decode('utf-8'))
            stripe_event = event_data.get("detail", event_data)
            if "type" not in stripe_event and "data" in event_data:
                stripe_event = event_data
        
        event_type = stripe_event.get("type")
        logger.info(f"Processing webhook event type: {event_type}")
        
        if event_type == "checkout.session.completed":
            session = stripe_event["data"]["object"]
            payment_intent_id = session.get("payment_intent")
            
            logger.info(f"Checkout session completed. Payment Intent ID: {payment_intent_id}")
            
            if not payment_intent_id:
                logger.warning("No payment_intent_id in checkout session")
                return {"status": "ok"}

            transaction = db.query(PaymentTransaction).filter(
                PaymentTransaction.stripe_payment_intent_id == payment_intent_id
            ).first()

            # CREATE TRANSACTION IF IT DOESN'T EXIST
            if not transaction:
                logger.info(f"Transaction not found, creating new one for payment_intent: {payment_intent_id}")
                # Get company_id from session metadata or retrieve from Stripe
                company_id = None
                customer_id = session.get("customer")
                
                if customer_id:
                    company = db.query(Company).filter(
                        Company.stripe_customer_id == customer_id
                    ).first()
                    if company:
                        company_id = company.id
                        logger.info(f"Found company_id: {company_id} for customer: {customer_id}")
                    else:
                        logger.warning(f"No company found for customer_id: {customer_id}")
                
                # Get metadata from session
                metadata = session.get("metadata", {})
                transaction_type = metadata.get("transaction_type", "license_pack")
                
                # Retrieve payment intent to get amount and currency
                try:
                    payment_intent = gateway.retrieve_payment_intent(payment_intent_id)
                    amount = Decimal(str(payment_intent.amount / 100))
                    currency = payment_intent.currency.upper()
                    charge_id = payment_intent.latest_charge if hasattr(payment_intent, 'latest_charge') else None
                    invoice_id = session.get("invoice") or payment_intent.get("invoice")
                    print("invoice_id: ", invoice_id)
                    if not invoice_id and hasattr(payment_intent, 'charges') and payment_intent.charges.data:
                        invoice_id = getattr(payment_intent.charges.data[0], 'invoice', None)
                    logger.info(f"Extracted invoice_id: {invoice_id}")  # Add logging to debug
                except Exception as e:
                    logger.error(f"Error retrieving payment intent: {e}")
                    raise
                
                # Create the transaction
                transaction = PaymentTransaction(
                    company_id=company_id,
                    transaction_type=transaction_type,
                    amount=amount,
                    currency=currency,
                    status="succeeded",
                    stripe_payment_intent_id=payment_intent_id,
                    stripe_customer_id=customer_id,
                    stripe_charge_id=charge_id,    
                    stripe_invoice_id=invoice_id,
                    product_description=metadata.get("product_description"),
                    completed_at=datetime.utcnow(),
                )
                db.add(transaction)
                db.flush()  # Flush to get the transaction ID
                logger.info(f"Created transaction with ID: {transaction.id}")
                
                # Create license pack if applicable
                if transaction_type == "license_pack":
                    pack_type = metadata.get("pack_type")
                    if pack_type and pack_type in PACK_TYPE_MAP and company_id:
                        company = db.query(Company).filter(Company.id == company_id).first()
                        if company:
                            license_pack = LicensePack(
                                company_id=company.id,
                                pack_type=pack_type,
                                total_licenses=PACK_TYPE_MAP[pack_type]["total_licenses"],
                                price_paid=amount,
                                currency=currency,
                                stripe_payment_id=payment_intent_id,
                                stripe_invoice_id=session.get("invoice"),
                            )
                            db.add(license_pack)
                            db.flush()
                            transaction.license_pack_id = license_pack.id
                            logger.info(f"Created license pack with ID: {license_pack.id}")
                
                db.commit()
                logger.info(f"Successfully committed transaction to database")
                return {"status": "ok"}

            if transaction.status == "succeeded":
                logger.info(f"Transaction already succeeded, skipping update")
                return {"status": "ok"}

            # Update existing transaction
            logger.info(f"Updating existing transaction: {transaction.id}")
            payment_intent = gateway.retrieve_payment_intent(payment_intent_id)
            amount = Decimal(str(payment_intent.amount / 100))
            currency = payment_intent.currency.upper()
            charge_id = payment_intent.latest_charge if hasattr(payment_intent, 'latest_charge') else None
            if not invoice_id and hasattr(payment_intent, 'charges') and payment_intent.charges.data:
                invoice_id = getattr(payment_intent.charges.data[0], 'invoice', None)
            logger.info(f"Extracted invoice_id for update: {invoice_id}")  

            transaction.status = "succeeded"
            transaction.amount = amount
            transaction.currency = currency
            transaction.stripe_charge_id = charge_id
            invoice_id = session.get("invoice") or payment_intent.get("invoice") 
            transaction.completed_at = datetime.utcnow()

            metadata = session.get("metadata", {})
            transaction_type = metadata.get("transaction_type", "license_pack")

            if transaction_type == "license_pack":
                pack_type = metadata.get("pack_type")
                if pack_type and pack_type in PACK_TYPE_MAP:
                    company = db.query(Company).filter(Company.id == transaction.company_id).first()
                    if company:
                        license_pack = LicensePack(
                            company_id=company.id,
                            pack_type=pack_type,
                            total_licenses=PACK_TYPE_MAP[pack_type]["total_licenses"],
                            price_paid=amount,
                            currency=currency,
                            stripe_payment_id=payment_intent_id,
                            stripe_invoice_id=session.get("invoice"),
                        )
                        db.add(license_pack)
                        db.flush()
                        transaction.license_pack_id = license_pack.id

            db.commit()
            logger.info(f"Successfully updated transaction: {transaction.id}")
            return {"status": "ok"}

        elif event_type == "payment_intent.payment_failed":
            payment_intent = stripe_event["data"]["object"]
            payment_intent_id = payment_intent.get("id")

            transaction = db.query(PaymentTransaction).filter(
                PaymentTransaction.stripe_payment_intent_id == payment_intent_id
            ).first()

            if transaction and transaction.status != "failed":
                transaction.status = "failed"
                transaction.failed_at = datetime.utcnow()
                transaction.failure_reason = payment_intent.get("last_payment_error", {}).get("message")
                db.commit()

            return {"status": "ok"}

        elif event_type == "charge.refunded":
            charge = stripe_event["data"]["object"]
            payment_intent_id = charge.get("payment_intent")

            transaction = db.query(PaymentTransaction).filter(
                PaymentTransaction.stripe_payment_intent_id == payment_intent_id
            ).first()

            if transaction:
                refund_amount = Decimal(str(charge.get("amount_refunded", 0) / 100))
                transaction.status = "refunded"
                transaction.refunded_at = datetime.utcnow()
                transaction.refund_amount = refund_amount
                db.commit()

            return {"status": "ok"}

        logger.info(f"Unhandled event type: {event_type}")
        return {"status": "ok"}
        
    except Exception as e:
        logger.error(f"Error processing webhook: {e}", exc_info=True)
        # Still return 200 to prevent Stripe from retrying
        return {"status": "error", "message": str(e)}



@router.get("/payment-success")
def payment_success():
    return {"status": "successfully completed"}


@router.get("/payment-cancel")
def payment_success():
    return {"status": "successfully cancelled"}


@router.get("/license-packs", response_model=list[LicensePackRead])
def get_license_packs(company_id: Optional[UUID] = None, id: Optional[UUID] = None,db: Session = Depends(get_db)):
    query = db.query(LicensePack)

    if id:
        query = query.filter(LicensePack.id == id)
    elif company_id:
        query = query.filter(LicensePack.company_id == company_id)
    else: 
        raise HTTPException(status_code=400, detail="Either company_id or id must be provided")

    results = query.all() 
    if not results: 
        raise HTTPException(status_code=404, detail="No license packs found")

    return results

@router.get("/payment-transactions", response_model=list[PaymentTransactionRead])
def get_payment_transactions(
    company_id: Optional[UUID] = None,
    stripe_customer_id: Optional[str] = None,
    license_pack_id: Optional[UUID] = None,
    db: Session = Depends(get_db)
):
    query = db.query(PaymentTransaction)
    if company_id: 
        query = query.filter(PaymentTransaction.company_id == company_id)
    elif stripe_customer_id: 
        query = query.filter(PaymentTransaction.stripe_customer_id == stripe_customer_id)
    elif license_pack_id:
        query = query.filter(PaymentTransaction.license_pack_id == license_pack_id)
    else: 
        raise HTTPException(status_code=400, detail="Either company_id, stripe_customer_id, or license_pack_id must be provided")

    results = query.all() 
    if not results: 
        raise HTTPException(status_code=404, detail="No payment transactions found")
    return results