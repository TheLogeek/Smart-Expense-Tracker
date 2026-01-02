from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, filters
from models import SessionLocal
from services import BudgetService, ExpenseService, ProfileService, UserService, UserService
from .menu_handlers import back_to_main_menu_keyboard
import logging

logger = logging.getLogger(__name__)

# States for budget setting conversation
CHOOSE_BUDGET_PERIOD, ENTER_BUDGET_AMOUNT, CHOOSE_BUDGET_CATEGORY = range(3)

async def start_set_budget(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the budget setting conversation."""
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
            "Would you like to set a daily, weekly, or monthly budget?",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Daily", callback_data="budget_period_daily")],
                [InlineKeyboardButton("Weekly", callback_data="budget_period_weekly")],
                [InlineKeyboardButton("Monthly", callback_data="budget_period_monthly")],
                [InlineKeyboardButton("Cancel", callback_data="cancel")]
            ])
        )
    else:
        await update.message.reply_text(
            "Would you like to set a daily, weekly, or monthly budget?",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Daily", callback_data="budget_period_daily")],
                [InlineKeyboardButton("Weekly", callback_data="budget_period_weekly")],
                [InlineKeyboardButton("Monthly", callback_data="budget_period_monthly")],
                [InlineKeyboardButton("Cancel", callback_data="cancel")]
            ])
        )
    db_session.close()
    return CHOOSE_BUDGET_PERIOD

async def choose_budget_period(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the chosen budget period and asks for the amount."""
    query = update.callback_query
    await query.answer()

    period = query.data.split('_')[-1]
    context.user_data['budget_period'] = period
    
    await query.edit_message_text(
        f"You selected a {period} budget. Please enter the budget amount (e.g., 50000).",
        reply_markup=back_to_main_menu_keyboard()
    )
    return ENTER_BUDGET_AMOUNT

async def enter_budget_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the budget amount and asks for category or saves the budget."""
    try:
        amount = float(update.message.text)
        if amount <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text(
            "That's not a valid amount. Please enter a positive number.",
            reply_markup=back_to_main_menu_keyboard()
        )
        return ENTER_BUDGET_AMOUNT
    
    context.user_data['budget_amount'] = amount

    db_session = SessionLocal()
    expense_service = ExpenseService(db_session)
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

    categories = expense_service.get_categories(current_profile.id)
    db_session.close()

    keyboard = []
    for category in categories:
        keyboard.append([InlineKeyboardButton(category.name, callback_data=f"budget_category_{category.id}")])
    keyboard.append([InlineKeyboardButton("Overall Budget", callback_data="budget_category_none")]) # For overall budget
    keyboard.append([InlineKeyboardButton("Cancel", callback_data="cancel")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"You set a {context.user_data['budget_period']} budget of ₦{amount:,.2f}.\n"
        "Would you like to apply this to a specific category, or make it an overall budget?",
        reply_markup=reply_markup
    )
    return CHOOSE_BUDGET_CATEGORY

async def choose_budget_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saves the budget with the chosen category."""
    query = update.callback_query
    await query.answer()

    category_id = None
    category_name = "Overall"

    db_session = SessionLocal()
    expense_service = ExpenseService(db_session)
    profile_service = ProfileService(db_session)
    user_service = UserService(db_session) # Also get user service here
    user_telegram_id = update.effective_user.id
    user = user_service.get_user(user_telegram_id)
    current_profile = profile_service.get_current_profile(user_telegram_id)

    if not user or not current_profile:
        await query.edit_message_text(
            "An error occurred. Please try using the main menu buttons or /start again.",
            reply_markup=back_to_main_menu_keyboard()
        )
        db_session.close()
        return ConversationHandler.END

    if query.data != "budget_category_none":
        category_id = int(query.data.split('_')[-1])
        category = expense_service.get_category_by_id(category_id)
        if category:
            category_name = category.name
        else:
            await query.edit_message_text("Invalid category selected. Please try again.", reply_markup=back_to_main_menu_keyboard())
            db_session.close()
            return CHOOSE_BUDGET_CATEGORY

    budget_service = BudgetService(db_session)
    
    period = context.user_data['budget_period']
    amount = context.user_data['budget_amount']

    budget = budget_service.set_budget(current_profile.id, amount, period, category_id)

    await query.edit_message_text(
        f"Successfully set a {period} budget of ₦{amount:,.2f} for '{category_name}'.",
        reply_markup=back_to_main_menu_keyboard()
    )
    db_session.close()
    return ConversationHandler.END

async def cancel_budget_op(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels the budget setting conversation."""
    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text("Budget setting cancelled. Returning to main menu.", reply_markup=back_to_main_menu_keyboard())
    else:
        await update.message.reply_text("Budget setting cancelled. Returning to main menu.", reply_markup=back_to_main_menu_keyboard())
    return ConversationHandler.END
