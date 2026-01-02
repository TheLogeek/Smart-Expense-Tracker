import os
import logging
import datetime
from zoneinfo import ZoneInfo
from sqlalchemy.orm import Session
from models import Referral, User
from telegram import InlineKeyboardButton, InlineKeyboardMarkup # Import necessary classes
from telegram.ext import Application # Import Application

logger = logging.getLogger(__name__)

BASE_REFERRAL_LINK = "https://t.me/SmartExpenseTrackerMLBot?start=" # Placeholder, replace with actual bot username
AFRICA_LAGOS_TZ = ZoneInfo("Africa/Lagos") # Defined here for consistency

class ReferralService:
    def __init__(self, db_session: Session):
        self.db_session = db_session

    def generate_referral_link(self, user_telegram_id: int) -> str:
        return f"{BASE_REFERRAL_LINK}{user_telegram_id}"

    def record_referral(self, referrer_id: int, referred_id: int, application: Application): # Added application argument
        # Check if this referral already exists
        existing_referral = self.db_session.query(Referral).filter_by(
            referred_id=referred_id # Only check referred_id as a user can only be referred once
        ).first()
        
        if existing_referral:
            logger.info(f"Referral from {referrer_id} to {referred_id} already recorded. Not sending message.")
            return None # Referral already recorded

        referral = Referral(
            referrer_id=referrer_id,
            referred_id=referred_id,
            referral_date=datetime.datetime.utcnow()
        )
        self.db_session.add(referral)
        self.db_session.commit()
        self.db_session.refresh(referral)
        logger.info(f"Referral from {referrer_id} to {referred_id} recorded successfully.")
        
        # Send notification to referrer - for profile creation bonus.
        # This will be refined in grant_profile_creation_bonus, but for now just a simple message.
        self.send_referral_notification(referrer_id, referred_id, application, "profile_creation")

        return referral

    def _extend_user_pro_status(self, user: User, days_to_add: int) -> bool:
        """Helper to extend a user's Pro subscription or trial."""
        now_utc = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc) # UTC-aware current time
        extended = False

        if user.is_pro: # User is currently Pro (paid or trial)
            if user.subscription_plan == "pro_paid" and user.subscription_end_date:
                # Ensure subscription_end_date is timezone-aware for comparison, default to UTC if not
                current_end_date_utc = user.subscription_end_date.replace(tzinfo=datetime.timezone.utc) if user.subscription_end_date.tzinfo is None else user.subscription_end_date
                user.subscription_end_date = max(current_end_date_utc, now_utc) + datetime.timedelta(days=days_to_add)
                logger.info(f"Extended paid Pro subscription for user {user.telegram_id} by {days_to_add} days. New end date: {user.subscription_end_date}")
                extended = True
            elif user.subscription_plan == "pro_trial" and user.trial_end_date:
                # Ensure trial_end_date is timezone-aware for comparison, default to UTC if not
                current_end_date_utc = user.trial_end_date.replace(tzinfo=datetime.timezone.utc) if user.trial_end_date.tzinfo is None else user.trial_end_date
                user.trial_end_date = max(current_end_date_utc, now_utc) + datetime.timedelta(days=days_to_add)
                logger.info(f"Extended Pro trial for user {user.telegram_id} by {days_to_add} days. New end date: {user.trial_end_date}")
                extended = True
            else: # Should not happen if is_pro is True
                logger.warning(f"User {user.telegram_id} is_pro but has no valid subscription_plan/dates to extend.")
        else: # Free user, grant a Pro trial
            user.subscription_plan = "pro_trial"
            user.is_pro = True
            user.trial_start_date = now_utc
            user.trial_end_date = now_utc + datetime.timedelta(days=days_to_add)
            logger.info(f"Granted Pro trial for free user {user.telegram_id} for {days_to_add} days. End date: {user.trial_end_date}")
            extended = True
        
        if extended:
            self.db_session.add(user)
            self.db_session.commit()
            self.db_session.refresh(user)
        return extended
    
    async def send_referral_notification(self, referrer_id: int, referred_id: int, application: Application, bonus_type: str):
        """Sends a notification to the referrer about their bonus."""
        referrer_user = self.db_session.query(User).filter_by(telegram_id=referrer_id).first()
        referred_user = self.db_session.query(User).filter_by(telegram_id=referred_id).first()

        referred_name = referred_user.first_name if referred_user and referred_user.first_name else f"User {referred_id}"

        message = ""
        if bonus_type == "profile_creation":
            message = (
                f"🎉 Great news! Your friend {referred_name} just created their first profile!\n"
                f"You've received a **+10 day Pro bonus** for this referral!\n"
                f"Your new Pro expiry date is: {referrer_user.subscription_end_date.astimezone(AFRICA_LAGOS_TZ).strftime('%Y-%m-%d %H:%M:%S %Z%z')}"
            )
        elif bonus_type == "upgrade":
            message = (
                f"🚀 Fantastic! Your friend {referred_name} just upgraded to Pro!\n"
                f"You've received an **additional +10 day Pro bonus** for this!\n"
                f"Your new Pro expiry date is: {referrer_user.subscription_end_date.astimezone(AFRICA_LAGOS_TZ).strftime('%Y-%m-%d %H:%M:%S %Z%z')}"
            )
        
        keyboard = [[InlineKeyboardButton("🔙 Back to Main Menu", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        try:
            await application.bot.send_message(
                chat_id=referrer_id,
                text=message,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            logger.info(f"Sent referral bonus notification to referrer {referrer_id} for referred {referred_id}.")
        except Exception as e:
            logger.error(f"Failed to send referral notification to {referrer_id}: {e}")

    def grant_profile_creation_bonus(self, referred_id: int, application: Application, days_to_add: int = 10) -> bool: # Added application
        """Grants a bonus to the referrer when a referred user creates their first profile."""
        referral = self.db_session.query(Referral).filter_by(referred_id=referred_id).first()
        
        if not referral:
            logger.warning(f"No referral record found for referred_id {referred_id}.")
            return False

        if referral.profile_creation_reward_granted:
            logger.info(f"Profile creation reward already granted for referred_id {referred_id}. Skipping.")
            return False

        referrer = self.db_session.query(User).filter_by(telegram_id=referral.referrer_id).first()
        if not referrer:
            logger.error(f"Referrer with ID {referral.referrer_id} not found for referred_id {referred_id}.")
            return False
        
        if self._extend_user_pro_status(referrer, days_to_add):
            referral.profile_creation_reward_granted = True
            self.db_session.add(referral)
            self.db_session.commit()
            self.db_session.refresh(referral)
            logger.info(f"Profile creation bonus of {days_to_add} days granted to referrer {referrer.telegram_id} for referred {referred_id}.")
            # Send notification
            asyncio.create_task(self.send_referral_notification(referrer.telegram_id, referred_id, application, "profile_creation")) # Send async
            return True
        return False

    def grant_upgrade_bonus(self, referred_id: int, application: Application, days_to_add: int = 10) -> bool: # Added application
        """Grants a bonus to the referrer when a referred user makes an upgrade."""
        referral = self.db_session.query(Referral).filter_by(referred_id=referred_id).first()
        
        if not referral:
            logger.warning(f"No referral record found for referred_id {referred_id}.")
            return False

        referrer = self.db_session.query(User).filter_by(telegram_id=referral.referrer_id).first()
        if not referrer:
            logger.error(f"Referrer with ID {referral.referrer_id} not found for referred_id {referred_id}.")
            return False

        if self._extend_user_pro_status(referrer, days_to_add):
            referral.upgrade_bonuses_granted_count += 1
            self.db_session.add(referral)
            self.db_session.commit()
            self.db_session.refresh(referral)
            logger.info(f"Upgrade bonus of {days_to_add} days granted to referrer {referrer.telegram_id} for referred {referred_id}. Total upgrade bonuses: {referral.upgrade_bonuses_granted_count}.")
            # Send notification
            asyncio.create_task(self.send_referral_notification(referrer.telegram_id, referred_id, application, "upgrade")) # Send async
            return True
        return False