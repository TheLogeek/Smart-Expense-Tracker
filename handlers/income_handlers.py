from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from models import SessionLocal
from services import IncomeService, ProfileService, UserService
from utils.misc_utils import get_currency_symbol # Import get_currency_symbol
from .menu_handlers import back_to_main_menu_keyboard
import logging

logger = logging.getLogger(__name__)

# States for income logging conversation
ENTER_INCOME_DETAILS = range(1)

async def start_income_logging(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the income logging conversation."""
    db_session = SessionLocal()
    profile_service = ProfileService(db_session)
    user_service = UserService(db_session)

    user_telegram_id = update.effective_user.id
    user = user_service.get_user(user_telegram_id)
    
    if not user:
        message = "It looks like you haven't started yet. Please use the /start command to begin!"
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.edit_message_text(message)
        else:
            await update.message.reply_text(message)
        db_session.close()
        return ConversationHandler.END

    current_profile = profile_service.get_current_profile(user_telegram_id)

    if not current_profile:
        message = "You need to select a profile first. Go to 'My Profile' -> 'View / Switch Profile' or 'Create New Profile'."
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.edit_message_text(message, reply_markup=back_to_main_menu_keyboard())
        else:
            await update.message.reply_text(message, reply_markup=back_to_main_menu_keyboard())
        db_session.close()
        return ConversationHandler.END

    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text(
            "Please enter your income details. E.g., '10000 from salary' or 'earned 5000 from freelance'.",
            reply_markup=back_to_main_menu_keyboard()
        )
    else:
        await update.message.reply_text(
            "Please enter your income details. E.g., '10000 from salary' or 'earned 5000 from freelance'.",
            reply_markup=back_to_main_menu_keyboard()
        )
    db_session.close()
    return ENTER_INCOME_DETAILS

async def enter_income_details(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Parses income details and saves the income."""
    text = update.message.text
    db_session = SessionLocal()
    income_service = IncomeService(db_session)
    profile_service = ProfileService(db_session)
    user_service = UserService(db_session) # Also get user service here

    user_telegram_id = update.effective_user.id
    user = user_service.get_user(user_telegram_id)
    current_profile = profile_service.get_current_profile(user_telegram_id)
    
    if not user or not current_profile:
        await update.message.reply_text(
            "An error occurred. Please try using the main menu buttons or /start again.",
            reply_markup=back_to_main_menu_keyboard()
        )
        db_session.close()
        return ConversationHandler.END

    amount, source = income_service.parse_income_message(text)
    
    if amount is None or source is None:
        await update.message.reply_text(
            "I couldn't understand that format. Please try again. "
            "E.g., '10000 from salary' or 'earned 5000 from freelance'.",
            reply_markup=back_to_main_menu_keyboard()
        )
        db_session.close()
        return ENTER_INCOME_DETAILS

    income_service.add_income(current_profile.id, amount, source)
    
    currency_symbol = get_currency_symbol(current_profile.currency)

    await update.message.reply_text(
        f"Income of {currency_symbol}{amount:,} from {source} saved successfully!",
        reply_markup=back_to_main_menu_keyboard()
    )
    db_session.close()
    return ConversationHandler.END

async def cancel_income(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels the income logging conversation."""
    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text("Income logging cancelled. Returning to main menu.", reply_markup=back_to_main_menu_keyboard())
    else:
        await update.message.reply_text("Income logging cancelled. Returning to main menu.", reply_markup=back_to_main_menu_keyboard())
    return ConversationHandler.END