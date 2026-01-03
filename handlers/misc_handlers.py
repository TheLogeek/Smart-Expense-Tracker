from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, filters
from models import SessionLocal
from services import ProfileService, UserService, ReportService, ReferralService, MONTHLY_PRO_PRICE, YEARLY_PRO_PRICE, YEARLY_SAVINGS_NAIRA, YEARLY_SAVINGS_PERCENT
from .menu_handlers import back_to_main_menu_keyboard
import logging
import io
import datetime

logger = logging.getLogger(__name__)

# States for profile creation conversation
CREATE_PROFILE_TYPE, ASK_PROFILE_NAME = range(2)

async def start_create_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the profile creation conversation by asking for the profile type."""
    query = update.callback_query
    
    message_text = "What type of profile would you like to create?"
    reply_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("Personal", callback_data="profile_type_personal")],
        [InlineKeyboardButton("Business", callback_data="profile_type_business")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]
    ])

    if query:
        await query.answer()
        # Check if the message is already the type selection to avoid editing to the same content
        if query.message.text != message_text:
            await query.edit_message_text(message_text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(message_text, reply_markup=reply_markup)
    
    return CREATE_PROFILE_TYPE

async def create_profile_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the chosen profile type and asks for the profile name."""
    query = update.callback_query
    await query.answer()
    
    profile_type = query.data.split('_')[-1]
    context.user_data['profile_type'] = profile_type

    await query.edit_message_text(
        f"You selected a '{profile_type.capitalize()}' profile. What would you like to name it? (e.g., 'My Personal', 'Work Expenses')",
        reply_markup=back_to_main_menu_keyboard()
    )
    return ASK_PROFILE_NAME

async def create_profile_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the profile name and creates the profile."""
    profile_name = update.message.text
    profile_type = context.user_data['profile_type'] # Retrieve stored type
    
    db_session = SessionLocal()
    profile_service = ProfileService(db_session)
    user_service = UserService(db_session) # Instantiate UserService
    referral_service = ReferralService(db_session) # Instantiate ReferralService

    user_telegram_id = update.effective_user.id
    user = user_service.get_user(user_telegram_id) # Get the User object

    new_profile = profile_service.create_profile(user_telegram_id, profile_name, profile_type)

    if new_profile:
        message = f"Successfully created your '{profile_name}' ({profile_type}) profile!"
        # Check if user was referred and grant bonus if applicable
        if user and user.referred_by_info: # user.referred_by_info is a Referral object if referred
            if referral_service.grant_profile_creation_bonus(user_telegram_id):
                logger.info(f"Profile creation bonus granted for referrer of {user_telegram_id}.")
            else:
                logger.info(f"Profile creation bonus not granted/already granted for referrer of {user_telegram_id}.")
    else:
        message = "You have reached the maximum number of profiles for a free account. Please upgrade to Pro to create more."
    
    await update.message.reply_text(message, reply_markup=back_to_main_menu_keyboard())
    db_session.close()
    return ConversationHandler.END

async def switch_profile_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Displays user's profiles and allows them to switch."""
    query = update.callback_query
    await query.answer()

    db_session = SessionLocal()
    profile_service = ProfileService(db_session)
    user_telegram_id = update.effective_user.id
    profiles = profile_service.get_profiles(user_telegram_id)

    if not profiles:
        await query.edit_message_text(
            "You don't have any profiles yet. Let's create one!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Create Profile", callback_data="create_new_profile")]])
        )
        db_session.close()
        return ConversationHandler.END

    keyboard = []
    for profile in profiles:
        keyboard.append([InlineKeyboardButton(f"{profile.name} ({profile.profile_type})", callback_data=f"switch_profile_{profile.id}")])
    keyboard.append([InlineKeyboardButton("Back to Main Menu", callback_data="main_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        "Select a profile to switch to:",
        reply_markup=reply_markup
    )
    db_session.close()
    return ConversationHandler.END

async def features_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Displays the features of the bot for Free and Pro plans."""
    query = update.callback_query
    await query.answer()

    message = (
        "<b>✨ Bot Features:</b>\n\n"
        "<b>🆓 Free Plan:</b>\n"
        "  - Log Expenses (150/month limit)\n"
        "  - Log Income\n"
        "  - Daily, Weekly, Monthly Summaries (No visual representation)\n"
        "  - Set Budget\n"
        "  - 3 custom categories limit\n"
        "  - Toggle Daily Reminders\n"
        "  - Referral Program\n\n"
        "<b>🚀 Pro Plan:</b>\n"
        "  - Unlimited Expense Logging\n"
        "  - Log Expense from Receipt (OCR)\n"
        "  - Log Income\n"
        "  - Daily, Weekly, Monthly Summaries\n"
        "  - Detailed Charts & Analytics\n"
        "  - Set Budget\n"
        "  - Unlimited custom categories\n"
        "  - Toggle Daily Reminders\n"
        "  - Export Logs (CSV)\n"
        "  - Daily, weekly and monthly budget Insights\n"
        "  - Referral Program\n"
        f"  - Monthly Pro: ₦{MONTHLY_PRO_PRICE:,}\n"
        f"  - Yearly Pro: ₦{YEARLY_PRO_PRICE:,} (Save ₦{YEARLY_SAVINGS_NAIRA:,} - {YEARLY_SAVINGS_PERCENT}%)"
    )
    await query.edit_message_text(message, parse_mode='HTML', reply_markup=back_to_main_menu_keyboard())
    return ConversationHandler.END

async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Displays comprehensive help content."""
    query = update.callback_query
    await query.answer()

    help_message = (
        "<b>📚 Smart Expense Tracker Bot Help:</b>\n\n"
        
        "<b>Expense Logging:</b>\n"
        "  - Click '💸 Log Expense' then type: 'paid [amount] for [description]' (e.g., 'paid 5000 for fuel') or '[amount] for [description]' (e.g., '5000 for fuel').\n"
        "  - To log from a receipt (Pro feature), simply upload a photo of your receipt.\n\n"
        
        "<b>Income Logging:</b>\n"
        "  - Click '💰 Log Income' then type: '[amount] from [source]' (e.g., '10000 from salary') or 'earned [amount] from [source]' (e.g., 'earned 5000 from freelance').\n\n"
        
        "<b>Summaries:</b>\n"
        "  - Click '📊 Generate Summary' to see daily, weekly, or monthly breakdowns of your finances. Pro users get detailed charts.\n\n"
        
        "<b>Profiles:</b>\n"
        "  - Click '👤 My Profile' to '👀 View / Switch Profile' or '➕ Create New Profile'. Free users can have 1 profile, Pro users unlimited.\n\n"
        
        "<b>Budgeting:</b>\n"
        "  - Click '🎯 Set Budget' to create daily, weekly, or monthly budgets for specific categories or overall spending.\n\n"
        
        "<b>Export Logs (Pro):</b>\n"
        "  - Pro users can '📤 Export Logs (CSV)' to get a detailed CSV file of all transactions.\n\n"
        
        "<b>Referral Program:</b>\n"
        "  - Click '🤝 Refer a Friend' to get your unique referral link. Earn Pro days when friends upgrade!\n\n"
        
        "<b>Daily Reminders:</b>\n"
        "  - '⏰ Toggle Daily Reminders' to turn on/off friendly nudges to log your expenses.\n\n"
        
        "<b>Upgrade to Pro:</b>\n"
        "  - Unlock all features! Click '🚀 Upgrade to Pro' for options.\n\n"
        
        "If you need further assistance, please contact support."
    )
    await query.edit_message_text(help_message, parse_mode='HTML', reply_markup=back_to_main_menu_keyboard())
    return ConversationHandler.END

async def export_logs_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Generates and sends a CSV file of all logs for Pro users."""
    query = update.callback_query
    await query.answer("Generating export file...")

    db_session = SessionLocal()
    user_service = UserService(db_session)
    profile_service = ProfileService(db_session)
    report_service = ReportService(db_session)

    user_telegram_id = update.effective_user.id
    user = user_service.get_user(user_telegram_id)
    
    if not user:
        message = "It looks like you haven't started yet. Please use the /start command to begin!"
        if update.callback_query:
            await query.edit_message_text(message)
        else: # Should not happen from callback query
            await context.bot.send_message(chat_id=update.effective_chat.id, text=message)
        db_session.close()
        return ConversationHandler.END

    current_profile = profile_service.get_current_profile(user.telegram_id)

    if not current_profile:
        await query.edit_message_text(
            "You need to select a profile first to export logs. Go to 'My Profile' -> 'View / Switch Profile' or 'Create New Profile'.",
            reply_markup=back_to_main_menu_keyboard()
        )
        db_session.close()
        return ConversationHandler.END

    if not user.is_pro:
        await query.edit_message_text(
            "Exporting logs is a Pro feature. Please upgrade to Pro to use this functionality.",
            reply_markup=back_to_main_menu_keyboard()
        )
        db_session.close()
        return ConversationHandler.END
    
    csv_data_io = report_service.generate_csv_report(current_profile.id)
    csv_file_name = f"expense_income_report_{current_profile.name}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.csv"

    await context.bot.send_document(
        chat_id=update.effective_chat.id,
        document=InputFile(csv_data_io, filename=csv_file_name),
        caption=f"Your expense and income report for profile '{current_profile.name}' is ready!",
        reply_markup=back_to_main_menu_keyboard()
    )
    
    db_session.close()
    return ConversationHandler.END

async def switch_profile_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Displays user's profiles and allows them to switch."""
    query = update.callback_query
    await query.answer()

    db_session = SessionLocal()
    profile_service = ProfileService(db_session)
    user_telegram_id = update.effective_user.id
    profiles = profile_service.get_profiles(user_telegram_id)

    if not profiles:
        await query.edit_message_text(
            "You don't have any profiles yet. Let's create one!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Create Profile", callback_data="create_new_profile")]])
        )
        db_session.close() #close db
        return ConversationHandler.END

    keyboard = []
    for profile in profiles:
        keyboard.append([InlineKeyboardButton(f"{profile.name} ({profile.profile_type})", callback_data=f"switch_profile_{profile.id}")])
    keyboard.append([InlineKeyboardButton("Back to Main Menu", callback_data="main_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        "Select a profile to switch to:",
        reply_markup=reply_markup
    )
    db_session.close()
    return ConversationHandler.END

async def features_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Displays the features of the bot for Free and Pro plans."""
    query = update.callback_query
    await query.answer()

    message = (
        "<b>✨ Bot Features:</b>\n\n"
        "<b>🆓 Free Plan:</b>\n"
        "  - Log Expenses (150/month limit)\n"
        "  - Log Income\n"
        "  - Daily, Weekly, Monthly Summaries (No visual representation)\n"
        "  - Set Budget\n"
        "  - Limit of one profile\n"
        "  - Toggle Daily Reminders\n"
        "  - Referral Program\n\n"
        "<b>🚀 Pro Plan:</b>\n"
        "  - Unlimited Expense Logging\n"
        "  - Log Expense from Receipt (OCR)\n"
        "  - Log Income\n"
        "  - Daily, Weekly, Monthly Summaries\n"
        "  - Detailed Charts & Analytics\n"
        "  - Set Budget\n"
        "  - Unlimited profiles (personal & business) \n"
        "  - Toggle Daily Reminders\n"
        "  - Export Logs (CSV)\n"
        "  - Daily, weekly and monthly budget Insights\n"
        "  - Referral Program\n"
        f"  - Monthly Pro: ₦{MONTHLY_PRO_PRICE:,}\n"
        f"  - Yearly Pro: ₦{YEARLY_PRO_PRICE:,} (Save ₦{YEARLY_SAVINGS_NAIRA:,} - {YEARLY_SAVINGS_PERCENT}%)"
    )
    await query.edit_message_text(message, parse_mode='HTML', reply_markup=back_to_main_menu_keyboard())
    return ConversationHandler.END

async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Displays comprehensive help content."""
    query = update.callback_query
    await query.answer()

    help_message = (
        "<b>📚 Smart Expense Tracker Bot Help:</b>\n\n"
        
        "<b>Expense Logging:</b>\n"
        "  - Click '💸 Log Expense' then type: 'paid [amount] for [description]' (e.g., 'paid 5000 for fuel') or '[amount] for [description]' (e.g., '5000 for fuel').\n"
        "  - To log from a receipt (Pro feature), simply upload a photo of your receipt.\n\n"
        
        "<b>Income Logging:</b>\n"
        "  - Click '💰 Log Income' then type: '[amount] from [source]' (e.g., '10000 from salary') or 'earned [amount] from [source]' (e.g., 'earned 5000 from freelance').\n\n"
        
        "<b>Summaries:</b>\n"
        "  - Click '📊 Generate Summary' to see daily, weekly, or monthly breakdowns of your finances. Pro users get detailed charts.\n\n"
        
        "<b>Profiles:</b>\n"
        "  - Click '👤 My Profile' to '👀 View / Switch Profile' or '➕ Create New Profile'. Free users can have 1 profile, Pro users unlimited.\n\n"
        
        "<b>Budgeting:</b>\n"
        "  - Click '🎯 Set Budget' to create daily, weekly, or monthly budgets for specific categories or overall spending.\n\n"
        
        "<b>Export Logs (Pro):</b>\n"
        "  - Pro users can '📤 Export Logs (CSV)' to get a detailed CSV file of all transactions.\n\n"
        
        "<b>Referral Program:</b>\n"
        "  - Click '🤝 Refer a Friend' to get your unique referral link. Earn Pro days when friends upgrade!\n\n"
        
        "<b>Daily Reminders:</b>\n"
        "  - '⏰ Toggle Daily Reminders' to turn on/off friendly nudges to log your expenses.\n\n"
        
        "<b>Upgrade to Pro:</b>\n"
        "  - Unlock all features! Click '🚀 Upgrade to Pro' for options.\n\n"
        
        "If you need further assistance, please contact support."
    )
    await query.edit_message_text(help_message, parse_mode='HTML', reply_markup=back_to_main_menu_keyboard())
    return ConversationHandler.END

async def export_logs_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Generates and sends a CSV file of all logs for Pro users."""
    query = update.callback_query
    await query.answer("Generating export file...")

    db_session = SessionLocal()
    user_service = UserService(db_session)
    profile_service = ProfileService(db_session)
    report_service = ReportService(db_session)

    user_telegram_id = update.effective_user.id
    user = user_service.get_user(user_telegram_id)
    
    if not user:
        message = "It looks like you haven't started yet. Please use the /start command to begin!"
        if update.callback_query:
            await query.edit_message_text(message)
        else: # Should not happen from callback query
            await context.bot.send_message(chat_id=update.effective_chat.id, text=message)
        db_session.close()
        return ConversationHandler.END

    current_profile = profile_service.get_current_profile(user.telegram_id)

    if not current_profile:
        await query.edit_message_text(
            "You need to select a profile first to export logs. Go to 'My Profile' -> 'View / Switch Profile' or 'Create New Profile'.",
            reply_markup=back_to_main_menu_keyboard()
        )
        db_session.close()
        return ConversationHandler.END

    if not user.is_pro:
        await query.edit_message_text(
            "Exporting logs is a Pro feature. Please upgrade to Pro to use this functionality.",
            reply_markup=back_to_main_menu_keyboard()
        )
        db_session.close()
        return ConversationHandler.END
    
    csv_data_io = report_service.generate_csv_report(current_profile.id)
    csv_file_name = f"expense_income_report_{current_profile.name}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.csv"

    await context.bot.send_document(
        chat_id=update.effective_chat.id,
        document=InputFile(csv_data_io, filename=csv_file_name),
        caption=f"Your expense and income report for profile '{current_profile.name}' is ready!",
        reply_markup=back_to_main_menu_keyboard()
    )
    
    db_session.close()
    return ConversationHandler.END