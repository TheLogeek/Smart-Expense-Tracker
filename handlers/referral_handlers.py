from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from models import SessionLocal
from services import ReferralService
from .menu_handlers import back_to_main_menu_keyboard
import logging

logger = logging.getLogger(__name__)

async def generate_referral_link_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Generates and sends the user's unique referral link."""
    query = update.callback_query
    await query.answer()

    db_session = SessionLocal()
    referral_service = ReferralService(db_session)
    user_telegram_id = update.effective_user.id

    referral_link = referral_service.generate_referral_link(user_telegram_id)

    message = (
        f"Here's your unique referral link:\n"
        f"<code>{referral_link}</code>\n\n"
        f"Share this link with your friends! When they sign up using your link, "
        f"they get an extended 17-day Pro trial, and you get +10 Pro days "
        f"when they create their first profile and "
        f"for every successful upgrade they make!"
    )

    await query.edit_message_text(message, parse_mode='HTML', reply_markup=back_to_main_menu_keyboard())
    db_session.close()
    return ConversationHandler.END
