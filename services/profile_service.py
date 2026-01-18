from sqlalchemy.orm import Session
from models import Profile, User
from services.user_service import UserService
from services.referral_service import ReferralService # Import ReferralService
from telegram.ext import Application # Import Application

class ProfileService:
    def __init__(self, db_session: Session):
        self.db_session = db_session
        self.user_service = UserService(db_session)
        self.referral_service = ReferralService(db_session) # Initialize ReferralService

    def create_profile(self, user_telegram_id: int, name: str, profile_type: str, currency: str, application: Application = None) -> Profile: # Added currency and application
        user = self.user_service.get_user(user_telegram_id)
        if not user:
            return None

        # Enforce profile limits
        if not user.is_pro and len(user.profiles) >= 1:
            return None # Free users can only have one profile

        new_profile = Profile(
            user_id=user_telegram_id,
            name=name,
            profile_type=profile_type,
            currency=currency
        )
        self.db_session.add(new_profile)
        self.db_session.commit()
        self.db_session.refresh(new_profile)

        # If this is the user's first profile, set it as current
        if not user.current_profile_id:
            user.current_profile_id = new_profile.id
            self.db_session.add(user)
            self.db_session.commit()
            self.db_session.refresh(user)

            # Check if the user was referred and this is their first profile creation
            if user.referred_by:
                # Grant referrer reward (10 Pro days)
                self.referral_service.grant_profile_creation_bonus(referred_id=user_telegram_id, application=application, days_to_add=10) # Updated call

        return new_profile

    def get_profiles(self, user_telegram_id: int):
        user = self.user_service.get_user(user_telegram_id)
        if user:
            return user.profiles
        return []

    def get_profile_by_id(self, profile_id: int):
        return self.db_session.query(Profile).filter(Profile.id == profile_id).first()

    def get_current_profile(self, user_telegram_id: int):
        user = self.user_service.get_user(user_telegram_id)
        if user and user.current_profile_id:
            return self.get_profile_by_id(user.current_profile_id)
        return None

    def switch_profile(self, user_telegram_id: int, profile_id: int) -> bool:
        user = self.user_service.get_user(user_telegram_id)
        profile = self.get_profile_by_id(profile_id)
        
        if user and profile and profile.user_id == user_telegram_id:
            user.current_profile_id = profile_id
            self.db_session.add(user)
            self.db_session.commit()
            return True
        return False
