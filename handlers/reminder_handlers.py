from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, filters
from models import SessionLocal
from services import ReminderService, UserService
from .menu_handlers import back_to_main_menu_keyboard
import logging
import datetime

logger = logging.getLogger(__name__)

# States for reminder conversation
SET_REMINDER_TIME = range(1)

async def manage_reminders_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Displays the menu for managing reminders."""
    query = update.callback_query
    await query.answer()

    db_session = SessionLocal()
    user_service = UserService(db_session)
    user = user_service.get_user(update.effective_user.id)
    
    status = "ON" if user.daily_reminders_enabled else "OFF"
    time_str = user.reminder_time.strftime("%I:%M %p") if user.reminder_time else "Not Set"

    message = (
        f"Your daily reminders are currently **{status}**.\n"
        f"Current reminder time: **{time_str}** (WAT)\n\n"
        "What would you like to do?"
    )
    
    keyboard = [
        [InlineKeyboardButton("🔄 Turn On/Off", callback_data="toggle_daily_reminders")],
        [InlineKeyboardButton("⏰ Change Time", callback_data="change_reminder_time")],
        [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')
    db_session.close()
    return ConversationHandler.END # End here, handlers will be separate

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

    # After toggling, show the manage reminders menu again
    user_service = UserService(db_session)
    user = user_service.get_user(user_telegram_id)
    status = "ON" if user.daily_reminders_enabled else "OFF"
    time_str = user.reminder_time.strftime("%I:%M %p") if user.reminder_time else "Not Set"

    message = (
        f"Daily reminders are now **{status}**.\n"
        f"Current reminder time: **{time_str}** (WAT)\n\n"
        "What would you like to do?"
    )
    
    keyboard = [
        [InlineKeyboardButton("🔄 Turn On/Off", callback_data="toggle_daily_reminders")],
        [InlineKeyboardButton("⏰ Change Time", callback_data="change_reminder_time")],
        [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')

    db_session.close()
    return ConversationHandler.END

async def prompt_for_reminder_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Prompts the user to enter their preferred reminder time."""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "Please enter your preferred reminder time in 24-hour format (e.g., 08:30 or 21:00).",
        reply_markup=back_to_main_menu_keyboard()
    )
    return SET_REMINDER_TIME

async def set_reminder_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Parses and sets the new reminder time."""
    time_str = update.message.text.strip()
    
    try:
        # Parse time in HH:MM format
        new_time = datetime.datetime.strptime(time_str, "%H:%M").time()
        
        db_session = SessionLocal()
        reminder_service = ReminderService(db_session)
        user_telegram_id = update.effective_user.id
        
        reminder_service.set_reminder_time(user_telegram_id, new_time)
        
        await update.message.reply_text(
            f"Your reminder time has been updated to {new_time.strftime('%I:%M %p')} WAT.",
            reply_markup=back_to_main_menu_keyboard()
        )
        db_session.close()
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text(
            "Invalid time format. Please use 24-hour format (e.g., 08:30 or 21:00).",
            reply_markup=back_to_main_menu_keyboard()
        )
        return SET_REMINDER_TIME