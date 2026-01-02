from sqlalchemy.orm import Session
from models import User, Payment # Import Payment model
import datetime
from dateutil.relativedelta import relativedelta # Import relativedelta
import zoneinfo
from zoneinfo import ZoneInfo
from payments import PaystackService
import logging

logger = logging.getLogger(__name__)

AFRICA_LAGOS_TZ = ZoneInfo("Africa/Lagos")

MONTHLY_PRO_PRICE = 500
YEARLY_PRO_PRICE = 5000
YEARLY_SAVINGS_NAIRA = (MONTHLY_PRO_PRICE * 12) - YEARLY_PRO_PRICE
YEARLY_SAVINGS_PERCENT = round((YEARLY_SAVINGS_NAIRA / (MONTHLY_PRO_PRICE * 12)) * 100) # Corrected calculation for yearly savings

class SubscriptionService:
    def __init__(self, db_session: Session):
        self.db_session = db_session
        self.paystack_service = PaystackService()

    def get_user_subscription_status(self, user_telegram_id: int):
        user = self.db_session.query(User).filter(User.telegram_id == user_telegram_id).first()
        if not user:
            return None

        now_utc = datetime.datetime.now(datetime.timezone.utc)

        # Helper function to ensure datetime is UTC-aware
        def ensure_utc_aware(dt: datetime.datetime) -> datetime.datetime:
            if dt is None:
                return None
            if dt.tzinfo is None:
                # Assume naive dates from old DB entries are UTC
                return dt.replace(tzinfo=datetime.timezone.utc)
            return dt

        if user.subscription_plan == "pro_trial":
            trial_end_date_utc = ensure_utc_aware(user.trial_end_date)
            if trial_end_date_utc and trial_end_date_utc > now_utc:
                return {
                    "plan": "Pro (Trial)",
                    "expires_at": trial_end_date_utc.astimezone(AFRICA_LAGOS_TZ),
                    "is_pro": True
                }
            else:
                user.is_pro = False
                user.subscription_plan = "free"
                user.subscription_duration = None # Reset subscription duration
                user.trial_start_date = None
                user.trial_end_date = None
                self.db_session.add(user)
                self.db_session.commit()
                return {
                    "plan": "Free",
                    "expires_at": None,
                    "is_pro": False
                }
        elif user.subscription_plan == "pro_paid":
            subscription_end_date_utc = ensure_utc_aware(user.subscription_end_date)
            if subscription_end_date_utc and subscription_end_date_utc > now_utc:
                return {
                    "plan": "Pro (Paid)",
                    "expires_at": subscription_end_date_utc.astimezone(AFRICA_LAGOS_TZ),
                    "is_pro": True
                }
            else:
                user.is_pro = False
                user.subscription_plan = "free"
                user.subscription_duration = None # Reset subscription duration
                user.subscription_start_date = None
                user.subscription_end_date = None
                self.db_session.add(user)
                self.db_session.commit()
                return {
                    "plan": "Free",
                    "expires_at": None,
                    "is_pro": False
                }
        else:
            return {
                "plan": "Free",
                "expires_at": None,
                "is_pro": False
            }

    def _calculate_new_subscription_end_date(self, user: User, duration_months: int):
        logger.info(f"--- _calculate_new_subscription_end_date for user {user.telegram_id} ---")
        logger.info(f"  Initial user.subscription_end_date: {user.subscription_end_date}")
        logger.info(f"  Initial user.trial_end_date: {user.trial_end_date}")

        now_utc = datetime.datetime.now(datetime.timezone.utc)
        logger.info(f"  now_utc: {now_utc}")
        
        # Helper function to ensure datetime is UTC-aware (copied for internal use or refactored)
        def ensure_utc_aware(dt: datetime.datetime) -> datetime.datetime:
            if dt is None:
                return None
            if dt.tzinfo is None:
                # Assume naive dates from old DB entries are UTC
                return dt.replace(tzinfo=datetime.timezone.utc)
            return dt

        current_end_date_utc = None
        if user.subscription_plan == "pro_paid" and user.subscription_end_date:
            current_end_date_utc = ensure_utc_aware(user.subscription_end_date)
            logger.info(f"  current_end_date_utc (from pro_paid): {current_end_date_utc}")
        elif user.subscription_plan == "pro_trial" and user.trial_end_date:
            current_end_date_utc = ensure_utc_aware(user.trial_end_date)
            logger.info(f"  current_end_date_utc (from pro_trial): {current_end_date_utc}")

        base_date_for_extension = None
        if current_end_date_utc and current_end_date_utc > now_utc:
            base_date_for_extension = current_end_date_utc
            logger.info(f"  base_date_for_extension set to current_end_date_utc (future): {base_date_for_extension}")
        else:
            base_date_for_extension = now_utc
            logger.info(f"  base_date_for_extension set to now_utc (not future/expired): {base_date_for_extension}")

        logger.info(f"  duration_months: {duration_months}")
        new_end_date_utc = base_date_for_extension + relativedelta(months=duration_months)
        logger.info(f"  Calculated new_end_date_utc: {new_end_date_utc}")
        logger.info(f"--- End _calculate_new_subscription_end_date ---")
        return new_end_date_utc


    def initiate_paystack_payment(self, user: User, plan_type: str, bot_username: str) -> dict:
        """
        Initializes a Paystack payment for the selected plan.
        """
        amount = 0
        duration_months = 0
        if plan_type == "monthly":
            amount = MONTHLY_PRO_PRICE
            duration_months = 1
        elif plan_type == "yearly":
            amount = YEARLY_PRO_PRICE
            duration_months = 12
        else:
            return {"status": False, "message": "Invalid plan type."}

        amount_kobo = amount * 100

        metadata = {
            "user_telegram_id": user.telegram_id,
            "plan_type": plan_type,
            "duration_months": duration_months
        }
        
        user_email = f"{user.username or user.telegram_id}@telegram.org"
        
        callback_url = f"https://t.me/{bot_username}"

        payment_response = self.paystack_service.initialize_payment(
            user_email, amount_kobo, metadata, callback_url=callback_url
        )

        if payment_response and payment_response["status"]:
            return {
                "status": True,
                "authorization_url": payment_response["data"]["authorization_url"],
                "reference": payment_response["data"]["reference"]
            }
        return {"status": False, "message": payment_response.get("message", "Unknown error")}

    def handle_successful_payment(self, reference: str) -> dict:
        """
        Verifies Paystack payment and upgrades the user.
        Returns a dictionary with status (bool) and message (str).
        """
        verification_response = self.paystack_service.verify_payment(reference)

        if not verification_response["status"]:
            return {
                "status": False,
                "message": f"Paystack API call failed: {verification_response.get('message', 'Unknown error during API call.')}"
            }

        if verification_response["data"]["status"] == "success":
            metadata = verification_response["data"]["metadata"]
            user_telegram_id = metadata["user_telegram_id"]
            plan_type = metadata["plan_type"]
            duration_months = int(metadata["duration_months"])

            user = self.db_session.query(User).filter(User.telegram_id == user_telegram_id).first()
            if not user:
                return {
                    "status": False,
                    "message": "User not found after successful payment verification. Contact support."
                }
            
            # Check if this payment reference has already been logged
            existing_payment = self.db_session.query(Payment).filter_by(reference=reference, status="successful").first()
            if existing_payment:
                logger.info(f"Payment reference {reference} already logged as successful. Skipping payment record creation.")
            else:
                # Log the payment
                new_payment = Payment(
                    user_id=user_telegram_id,
                    amount=MONTHLY_PRO_PRICE if plan_type == "monthly" else YEARLY_PRO_PRICE, # Use actual price here
                    plan_type=plan_type,
                    reference=reference,
                    status="successful"
                )
                self.db_session.add(new_payment)
                # No commit yet, commit with user update

            new_end_date = self._calculate_new_subscription_end_date(user, duration_months)

            user.is_pro = True
            user.subscription_plan = "pro_paid"
            user.subscription_start_date = datetime.datetime.now(datetime.timezone.utc)
            user.subscription_end_date = new_end_date
            user.subscription_duration = plan_type # Set the subscription duration
            user.trial_start_date = None
            user.trial_end_date = None

            self.db_session.add(user)
            self.db_session.commit()
            self.db_session.refresh(user)

            if user.referred_by_info:
                from services import ReferralService
                ref_service = ReferralService(self.db_session)
                ref_service.grant_upgrade_bonus(referred_id=user.telegram_id, days_to_add=10)

            return {
                "status": True,
                "message": "Payment verified successfully and subscription activated!"
            }
        else:
            return {
                "status": False,
                "message": f"Transaction status is '{verification_response['data']['status']}'. Gateway response: {verification_response['data'].get('gateway_response', 'N/A')}"
            }
    
    def get_users_with_expiring_subscriptions(self) -> list[User]:
        """
        Retrieves a list of users whose Pro trial or paid subscription
        is expiring within the next 24 hours (in AFRICA_LAGOS_TZ).
        """
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        next_24_hours_utc = now_utc + datetime.timedelta(days=1)

        expiring_users = self.db_session.query(User).filter(
            User.is_pro == True,
            (
                (User.subscription_plan == "pro_trial") & 
                (User.trial_end_date >= now_utc) & 
                (User.trial_end_date <= next_24_hours_utc)
            ) | (
                (User.subscription_plan == "pro_paid") & 
                (User.subscription_end_date >= now_utc) & 
                (User.subscription_end_date <= next_24_hours_utc)
            )
        ).all()
        return expiring_users

    def downgrade_expired_subscriptions(self) -> list[int]:
        """
        Identifies users whose trial or paid subscriptions have ended
        and downgrades them to free, returning their telegram_ids.
        """
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        downgraded_user_ids = []

        expired_trials = self.db_session.query(User).filter(
            User.subscription_plan == "pro_trial",
            User.trial_end_date <= now_utc,
            User.is_pro == True
        ).all()

        for user in expired_trials:
            user.is_pro = False
            user.subscription_plan = "free"
            user.subscription_duration = None # Reset subscription duration
            user.trial_start_date = None
            user.trial_end_date = None
            self.db_session.add(user)
            downgraded_user_ids.append(user.telegram_id)
            logger.info(f"User {user.telegram_id} (trial) downgraded to Free.")

        # Find expired Pro paid users
        expired_paid_subs = self.db_session.query(User).filter(
            User.subscription_plan == "pro_paid",
            User.subscription_end_date <= now_utc,
            User.is_pro == True
        ).all()

        for user in expired_paid_subs:
            user.is_pro = False
            user.subscription_plan = "free"
            user.subscription_duration = None # Reset subscription duration
            user.subscription_start_date = None
            user.subscription_end_date = None
            self.db_session.add(user)
            downgraded_user_ids.append(user.telegram_id)
            logger.info(f"User {user.telegram_id} (paid) downgraded to Free.")
        
        self.db_session.commit()
        return downgraded_user_ids