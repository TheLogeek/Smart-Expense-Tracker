import os
import json
import requests # Import the requests library
from dotenv import load_dotenv
import logging

logger = logging.getLogger(__name__)

load_dotenv()

class PaystackService:
    def __init__(self):
        self.secret_key = os.getenv("PAYSTACK_SECRET_KEY", 'YOUR_SECRET_KEY')
        self.base_url = "https://api.paystack.co"

        if not self.secret_key:
            raise ValueError("PAYSTACK_SECRET_KEY not found in environment variables.")

        self.headers = {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json"
        }

    def initialize_payment(self, email: str, amount_kobo: int, metadata: dict = None, callback_url: str = None) -> dict:
        """
        Initializes a payment transaction with Paystack using direct requests.
        Amount should be in kobo (e.g., 10000 for NGN 100.00).
        """
        url = f"{self.base_url}/transaction/initialize"
        
        payload = {
            "email": email,
            "amount": amount_kobo,
            "callback_url": callback_url, # Use the provided callback_url
            "metadata": metadata
        }
        try:
            response = requests.post(url, headers=self.headers, data=json.dumps(payload))
            response.raise_for_status() # Raise an exception for HTTP errors
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error initializing Paystack payment: {e}")
            return {"status": False, "message": str(e)}

    def verify_payment(self, transaction_reference: str) -> dict:
        """
        Verifies a Paystack transaction using its reference, as per your provided logic.
        """
        url = f"{self.base_url}/transaction/verify/{transaction_reference}" # Corrected URL structure
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)
            response_json = response.json()
            
            # Check the API call status first
            if response_json['status']:
                # The actual transaction status is in the 'data' object
                transaction_data = response_json['data']
                if transaction_data['status'] == 'success':
                    logger.info(f"Transaction {transaction_reference} verified successfully. Status: {transaction_data['status']}")
                    return response_json # Return the full response as expected by SubscriptionService
                else:
                    logger.warning(f"Transaction verification failed or status is not 'success' for reference {transaction_reference}. "
                                   f"Gateway response: {transaction_data.get('gateway_response', 'N/A')}")
                    return {"status": False, "message": transaction_data.get('gateway_response', 'Verification failed'), "data": transaction_data}
            else:
                logger.error(f"Paystack API call failed for reference {transaction_reference}: {response_json.get('message', 'Unknown API error')}")
                return {"status": False, "message": response_json.get('message', 'Unknown API error')}

        except requests.exceptions.RequestException as e:
            logger.error(f"An error occurred during Paystack verification for reference {transaction_reference}: {e}")
            return {"status": False, "message": str(e)}
