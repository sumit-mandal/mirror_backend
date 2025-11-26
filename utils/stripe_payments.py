from json import load
import os 
import stripe 
from dotenv import load_dotenv  

load_dotenv()

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")


stripe.api_key = STRIPE_SECRET_KEY
print(f"Stripe API key: {STRIPE_SECRET_KEY}")
print(f"Stripe Publishable key: {STRIPE_PUBLISHABLE_KEY}")

class StripeGateway:
    def __init__(self) -> None:
        self.client = stripe

    def create_customer(self, **kwargs):
        return self.client.Customer.create(**kwargs)
    
    def update_customer(self, customer_id: str, **kwargs):
        return self.client.Customer.modify(customer_id, **kwargs)

    def create_checkout_session(self, *,  
        customer_id: str,
        price_id: str,
        quantity: int,
        success_url: str,
        cancel_url: str,
        mode: str,
        metadata: dict[str, str] | None,):
            params = {
                "customer": customer_id,
                "line_items": [{"price": price_id, "quantity": quantity}],
                "mode": mode,
                "success_url": success_url,
                "cancel_url": cancel_url,
            }
            if metadata:
                params["metadata"] = metadata
                return self.client.checkout.Session.create(**params)

    def construct_webhook_event(self, payload: bytes, sig_header: str):
        return self.client.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )

    def retrieve_checkout_session(self, session_id: str):
        return self.client.checkout.Session.retrieve(session_id)

    def retrieve_payment_intent(self, intent_id: str):
        return self.client.PaymentIntent.retrieve(intent_id)

def get_publishable_key():
    return STRIPE_PUBLISHABLE_KEY

        