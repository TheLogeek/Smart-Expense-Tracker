from sqlalchemy.orm import Session
from models import User, Expense
import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup # Import necessary classes
from services.profile_service import ProfileService # Import ProfileService
from services.summary_service import SummaryService # Import SummaryService
from utils.datetime_utils import wat_day_bounds_utc # Import the new utility

def main_menu_keyboard():
    keyboard = [[InlineKeyboardButton("🔙 Back to Main Menu", callback_data="main_menu")]]
    return InlineKeyboardMarkup(keyboard)

class ReminderService:
    def __init__(self, db_session: Session):
        self.db_session = db_session
        self.profile_service = ProfileService(db_session)
        self.summary_service = SummaryService(db_session)

    def toggle_daily_reminders(self, user_telegram_id: int) -> bool:
        user = self.db_session.query(User).filter(User.telegram_id == user_telegram_id).first()
        if user:
            user.daily_reminders_enabled = not user.daily_reminders_enabled
            self.db_session.add(user)
            self.db_session.commit()
            self.db_session.refresh(user)
            return user.daily_reminders_enabled
        return False

    def has_logged_today(self, user_telegram_id: int) -> bool:
        start_of_day_utc, end_of_day_utc = wat_day_bounds_utc()
        
        current_profile = self.profile_service.get_current_profile(user_telegram_id)
        if not current_profile:
            return False # Cannot check if no profile is selected

        expense_logged = self.db_session.query(Expense).filter(
            Expense.profile_id == current_profile.id,
            Expense.date >= start_of_day_utc,
            Expense.date < end_of_day_utc # Use < for exclusive end
        ).first()
        
        return expense_logged is not None

    async def send_daily_reminder(self, application, user_telegram_id: int):
        # This method will be called by APScheduler
        db_session = self.db_session
        user = db_session.query(User).filter(User.telegram_id == user_telegram_id).first()
        
        if user and user.daily_reminders_enabled:
            if self.has_logged_today(user_telegram_id):
                # Send daily activity summary
                current_profile = self.profile_service.get_current_profile(user_telegram_id)
                summary_data = self.summary_service.get_daily_summary(current_profile.id)
                message = (
                    f"🌟 Here's your daily summary for {datetime.date.today().strftime('%b %d, %Y')}:\n\n"
                    f"💸 Expenses: ₦{summary_data['total_expenses']:,}\n"
                    f"💰 Income: ₦{summary_data['total_income']:,}\n\n"
                    "Keep up the great work!"
                )
                try:
                    await application.bot.send_message(
                        chat_id=user_telegram_id,
                        text=message,
                        reply_markup=main_menu_keyboard()
                    )
                    logger.info(f"Daily summary sent to user {user_telegram_id}")
                except Exception as e:
                    logger.error(f"Failed to send daily summary to user {user_telegram_id}: {e}")
            else:
                # Send reminder
                message = (
                    f"👋 Hey {user.first_name or 'there'}! Just a friendly reminder to log your expenses for today. "
                    "Keep track of your spending to stay on top of your finances! ✨"
                )
                try:
                    await application.bot.send_message(
                        chat_id=user_telegram_id,
                        text=message,
                        reply_markup=main_menu_keyboard()
                    )
                    logger.info(f"Daily reminder sent to user {user_telegram_id}")
                except Exception as e:
                    logger.error(f"Failed to send daily reminder to user {user_telegram_id}: {e}")
        db_session.close() # Close session for scheduled job

