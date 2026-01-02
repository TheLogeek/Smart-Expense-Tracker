from sqlalchemy.orm import Session
from models import User, SessionLocal
import datetime
from datetime import timezone # Import timezone
# Removed: from services import ReferralService # Moved inside function to break circular import
from telegram.ext import Application # Import Application
import logging # Import logging

logger = logging.getLogger(__name__) # Initialize logger

class UserService:
    def __init__(self, db_session: Session):
        self.db_session = db_session

    def get_or_create_user(self, telegram_id: int, username: str, first_name: str, last_name: str, referral_id: int = None, application: Application = None) -> User: # Added application argument
        user = self.db_session.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            trial_days = 14
            if referral_id:
                # Basic check for referral_id existence, can be expanded later
                referrer = self.db_session.query(User).filter(User.telegram_id == referral_id).first()
                if referrer:
                    trial_days = 17 # Extended trial for referred users

            trial_start = datetime.datetime.now(timezone.utc)
            trial_end = trial_start + datetime.timedelta(days=trial_days)

            user = User(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                is_pro=True, # New users get a Pro trial
                trial_start_date=trial_start,
                trial_end_date=trial_end,
                referred_by=referral_id,
                subscription_plan="pro_trial"
            )
            self.db_session.add(user)
            self.db_session.commit()
            self.db_session.refresh(user)

            # Create referral record AFTER user is created
            if referral_id and referral_id != telegram_id: # Prevent self-referral
                if application: # Only record referral if application is provided
                    from services import ReferralService # Local import to break circular dependency
                    ref_service = ReferralService(self.db_session)
                    ref_service.record_referral(referrer_id=referral_id, referred_id=telegram_id, application=application) # Pass application
                else:
                    logger.warning(f"Application instance not provided for referral record for referrer {referral_id}, referred {telegram_id}.")
            
            return user
        return user

    def get_user(self, telegram_id: int) -> User:
        return self.db_session.query(User).filter(User.telegram_id == telegram_id).first()

    def update_user(self, user: User) -> User:
        self.db_session.add(user)
        self.db_session.commit()
        self.db_session.refresh(user)
        return user
