from sqlalchemy.orm import Session
from sqlalchemy.orm import Session
from models import User, Expense
import datetime
import pytz
from services.profile_service import ProfileService # Import ProfileService

AFRICA_LAGOS = pytz.timezone('Africa/Lagos')

class ReminderService:
    def __init__(self, db_session: Session):
        self.db_session = db_session
        self.profile_service = ProfileService(db_session)

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
        now_local = datetime.datetime.now(AFRICA_LAGOS)
        start_of_day_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day_local = now_local.replace(hour=23, minute=59, second=59, microsecond=999999)

        start_of_day_utc = start_of_day_local.astimezone(pytz.utc).replace(tzinfo=None)
        end_of_day_utc = end_of_day_local.astimezone(pytz.utc).replace(tzinfo=None)
        
        current_profile = self.profile_service.get_current_profile(user_telegram_id)
        if not current_profile:
            return False # Cannot check if no profile is selected

        expense_logged = self.db_session.query(Expense).filter(
            Expense.profile_id == current_profile.id,
            Expense.date >= start_of_day_utc,
            Expense.date <= end_of_day_utc
        ).first()
        
        return expense_logged is not None

    async def send_daily_reminder(self, application, user_telegram_id: int):
        # This method will be called by APScheduler
        db_session = self.db_session
        user = db_session.query(User).filter(User.telegram_id == user_telegram_id).first()
        
        if user and user.daily_reminders_enabled and not self.has_logged_today(user_telegram_id):
            message = (
                f"👋 Hey {user.first_name or 'there'}! Just a friendly reminder to log your expenses for today. "
                "Keep track of your spending to stay on top of your finances! ✨"
            )
            # Send message via bot
            try:
                await application.bot.send_message(
                    chat_id=user_telegram_id,
                    text=message,
                    reply_markup=None # Can add keyboard here if needed
                )
                logger.info(f"Daily reminder sent to user {user_telegram_id}")
            except Exception as e:
                logger.error(f"Failed to send daily reminder to user {user_telegram_id}: {e}")
        db_session.close() # Close session for scheduled job

