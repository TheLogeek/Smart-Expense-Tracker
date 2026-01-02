from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from models import SessionLocal
from services import ReminderService
from .menu_handlers import back_to_main_menu_keyboard
import logging

logger = logging.getLogger(__name__)

async def toggle_daily_reminders_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Toggles the user's daily reminder setting."""
    query = update.callback_query
    await query.answer()

    db_session = SessionLocal()
    reminder_service = ReminderService(db_session)
    user_telegram_id = update.effective_user.id

    new_status = reminder_service.toggle_daily_reminders(user_telegram_id)

    status_text = "enabled" if new_status else "disabled"
    message = f"Daily reminders have been {status_text}."

    await query.edit_message_text(message, reply_markup=back_to_main_menu_keyboard())
    db_session.close()
    return ConversationHandler.END
