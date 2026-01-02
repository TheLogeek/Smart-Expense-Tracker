import os
import io
from dotenv import load_dotenv
import google.genai as genai
from google.genai.errors import APIError
from PIL import Image
import logging
import re
import json

logger = logging.getLogger(__name__)

load_dotenv()

# Use your provided logic to initialize the Gemini client and model
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    logging.error("GEMINI_API_KEY not found in .env file. OCR feature will not work.")
    raise ValueError("GEMINI_API_KEY environment variable not set.")

# Initialize the Gemini client as per your instruction
genai_client = genai.Client(api_key=GEMINI_API_KEY)


class OCRService:
    def __init__(self):
        # The client is now initialized at the module level as genai_client
        pass

    async def process_image_with_gemini_ocr(self, image_data: io.BytesIO) -> str:
        """
        Processes an image using Google Gemini for OCR and structured data extraction.
        """
        prompt_text = (
            "Extract the price/amount from this receipt image. "
            "Present it in this format: 'paid [amount] for N/A'. "
            "If a description is present in the receipt, return 'paid [amount] for [description]'. "
            "Tip: if you read a large number on the receipt and it begins with the naira sign or a currency sign, that is the amount/price, return only its numerical value, for example if you see ₦1000.00, that means the amount is 1000.00. "
            "If the image is not a valid receipt, return 'Image is not a valid receipt'."
        )
        
        try:
            image = Image.open(image_data)
            
            # Use the provided logic for making the API call
            response = genai_client.models.generate_content(model="gemini-2.5-flash",
                contents=[image, prompt_text] # Pass prompt and image in a list to content
            )

            response_text = response.text
            logger.info(f"Gemini API raw response: {response_text}")

            # If the response indicates an invalid receipt, return it directly
            return response.text


            # Parse the extracted information
            # The prompt now expects a string like "paid [amount] for [description]"
            # So we need to re-implement the parsing to extract amount, description, and potentially date
            amount_match = re.search(r"paid\s+(\d+(?:[.,]\d{1,2})?)\s+for\s+(.+)", response_text, re.IGNORECASE)
            
            extracted_amount = None
            extracted_description = None

            if amount_match:
                extracted_amount = float(amount_match.group(1).replace(',', ''))
                extracted_description = amount_match.group(2).strip()

            return json.dumps({
                'amount': extracted_amount,
                'description': extracted_description
            })

        except APIError as e:
            logging.error(f"Gemini API Error during OCR: {e}")
            return "OCR engine is unavailable.. Please use text logging for now."
        except Exception as e:
            logging.error(f"Error in process_image_with_gemini_ocr: {e}")
            return '{"error": "OCR engine encountered an unexpected error,please use text logging."}'
