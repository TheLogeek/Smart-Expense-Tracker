import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from models import SessionLocal
from services import ExpenseService, IncomeService, ProfileService
from .menu_handlers import back_to_main_menu_keyboard
import datetime
from utils.datetime_utils import to_wat, wat_day_bounds_utc, wat_week_bounds_utc, wat_month_bounds_utc # Import new utilities
from datetime import timezone # Import timezone for UTC

# States for transaction history pagination and clearing
VIEW_TRANSACTIONS, CLEAR_HISTORY_MENU, CONFIRM_CLEAR_HISTORY = range(3)

TRANSACTIONS_PER_PAGE = 5

async def transaction_history_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Displays the last N transactions and provides pagination buttons."""
    query = update.callback_query
    if query:
        await query.answer()

    db_session = SessionLocal()
    profile_service = ProfileService(db_session)
    expense_service = ExpenseService(db_session)
    income_service = IncomeService(db_session)

    user_telegram_id = update.effective_user.id
    current_profile = profile_service.get_current_profile(user_telegram_id)

    if not current_profile:
        message = "You need to select a profile first. Go to '👤 My Profile' -> '👀 View / Switch Profile' or '➕ Create New Profile'."
        if query:
            await query.edit_message_text(message, reply_markup=back_to_main_menu_keyboard())
        else:
            await update.message.reply_text(message, reply_markup=back_to_main_menu_keyboard())
        db_session.close()
        return ConversationHandler.END

    all_transactions = []
    expenses = expense_service.get_expenses_by_profile(current_profile.id)
    incomes = income_service.get_incomes_by_profile(current_profile.id)

    for exp in expenses:
        all_transactions.append({
            "type": "Expense",
            "date": exp.date,
            "amount": exp.amount,
            "description": exp.description,
            "category": exp.category.name if exp.category else "N/A"
        })
    for inc in incomes:
        all_transactions.append({
            "type": "Income",
            "date": inc.date,
            "amount": inc.amount,
            "description": inc.source,
            "category": "N/A"
        })

    # Sort transactions by date, newest first
    all_transactions.sort(key=lambda x: x['date'], reverse=True)
    context.user_data['all_transactions'] = all_transactions
    context.user_data['current_transaction_page'] = 0

    return await send_transactions_page(update, context)

async def send_transactions_page(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Sends the current page of transactions."""
    all_transactions = context.user_data['all_transactions']
    current_page = context.user_data['current_transaction_page']

    start_index = current_page * TRANSACTIONS_PER_PAGE
    end_index = start_index + TRANSACTIONS_PER_PAGE
    transactions_on_page = all_transactions[start_index:end_index]

    if not transactions_on_page and current_page == 0:
        message_text = "You have no transactions yet for this profile."
        keyboard_buttons = [[InlineKeyboardButton("🔙 Back to Main Menu", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard_buttons)
    elif not transactions_on_page:
        context.user_data['current_transaction_page'] -= 1 # Go back to previous page if empty
        return await send_transactions_page(update, context) # Resend previous page
    else:
        message_text = "<b>📊 Transaction History:</b>\n\n"
        for t in transactions_on_page:
            amount_str = f"₦{t['amount']:,}"
            type_emoji = "🔴" if t['type'] == "Expense" else "🟢"
            
            # --- START LOGGING ---
            logging.info(f"Before to_wat - Transaction Type: {t['type']}, Date: {t['date']}, TZInfo: {t['date'].tzinfo}, Type: {type(t['date'])}")
            # --- END LOGGING ---

            # Convert to WAT for display
            wat_date = to_wat(t['date'])
            
            # --- START LOGGING ---
            logging.info(f"After to_wat - Transaction Type: {t['type']}, Date: {wat_date}, TZInfo: {wat_date.tzinfo}, Type: {type(wat_date)}")
            # --- END LOGGING ---

            message_text += (
                f"{type_emoji} {amount_str} ({t['description']} - {wat_date.strftime('%b %d, %H:%M %Z%z')})\n"
            )
        
        message_text += f"\nPage {current_page + 1} of {((len(all_transactions) - 1) // TRANSACTIONS_PER_PAGE) + 1}"

        keyboard_buttons = []
        if current_page > 0:
            keyboard_buttons.append(InlineKeyboardButton("⬅️ Previous", callback_data="prev_transactions"))
        if end_index < len(all_transactions):
            keyboard_buttons.append(InlineKeyboardButton("➡️ Next", callback_data="next_transactions"))
        
        # Add Clear History button
        bottom_buttons = [
            InlineKeyboardButton("🧹 Clear History", callback_data="clear_history_menu"),
            InlineKeyboardButton("🔙 Back to Main Menu", callback_data="main_menu")
        ]
        
        # Ensure keyboard_buttons is always a list of lists before appending
        if keyboard_buttons:
            keyboard = [keyboard_buttons]
        else:
            keyboard = [] # No pagination buttons

        keyboard.append(bottom_buttons) # Add clear history and back button
        reply_markup = InlineKeyboardMarkup(keyboard)

    query = update.callback_query
    if query:
        await query.edit_message_text(message_text, parse_mode='HTML', reply_markup=reply_markup)
    else:
        await update.message.reply_html(message_text, reply_markup=reply_markup)
    
    return VIEW_TRANSACTIONS

async def show_next_transactions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Moves to the next page of transactions."""
    query = update.callback_query
    await query.answer()
    context.user_data['current_transaction_page'] += 1
    return await send_transactions_page(update, context)

async def show_prev_transactions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Moves to the previous page of transactions."""
    query = update.callback_query
    await query.answer()
    context.user_data['current_transaction_page'] -= 1
    return await send_transactions_page(update, context)

async def clear_history_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Displays options for clearing transaction history."""
    query = update.callback_query
    await query.answer()

    message_text = "What history would you like to clear? This action cannot be undone."
    keyboard = [
        [InlineKeyboardButton("Today", callback_data="clear_today")],
        [InlineKeyboardButton("This Week", callback_data="clear_week")],
        [InlineKeyboardButton("This Month", callback_data="clear_month")],
        [InlineKeyboardButton("All Transactions and Logs", callback_data="clear_all")],
        [InlineKeyboardButton("🔙 Back to Transaction History", callback_data="transaction_history")], # Back button
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(message_text, reply_markup=reply_markup, parse_mode='HTML')
    return CLEAR_HISTORY_MENU

async def execute_clear_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Executes the clearing of transaction history based on chosen period."""
    query = update.callback_query
    await query.answer("Clearing history...")

    db_session = SessionLocal()
    expense_service = ExpenseService(db_session)
    income_service = IncomeService(db_session)
    profile_service = ProfileService(db_session)

    user_telegram_id = update.effective_user.id
    current_profile = profile_service.get_current_profile(user_telegram_id)
    profile_id = current_profile.id if current_profile else None

    if not profile_id:
        await query.edit_message_text("Error: No active profile found to clear history.", reply_markup=back_to_main_menu_keyboard())
        db_session.close()
        return ConversationHandler.END

    clear_period = query.data.replace("clear_", "") # e.g., "today", "week", "month", "all"

    start_date_utc, end_date_utc = None, None
    period_description = ""

    if clear_period == "today":
        start_date_utc, end_date_utc = wat_day_bounds_utc()
        period_description = "today's"
    elif clear_period == "week":
        start_date_utc, end_date_utc = wat_week_bounds_utc()
        period_description = "this week's"
    elif clear_period == "month":
        start_date_utc, end_date_utc = wat_month_bounds_utc()
        period_description = "this month's"
    elif clear_period == "all":
        period_description = "all"
    else:
        await query.edit_message_text("Invalid clear period selected.", reply_markup=back_to_main_menu_keyboard())
        db_session.close()
        return ConversationHandler.END
    
    deleted_expenses_count = 0
    deleted_incomes_count = 0

    if clear_period == "all":
        deleted_expenses_count = expense_service.delete_all_expenses(profile_id)
        deleted_incomes_count = income_service.delete_all_incomes(profile_id)
    else:
        if start_date_utc and end_date_utc:
            deleted_expenses_count = expense_service.delete_expenses_by_date_range(profile_id, start_date_utc, end_date_utc)
            deleted_incomes_count = income_service.delete_incomes_by_date_range(profile_id, start_date_utc, end_date_utc)

    message_text = f"✅ Successfully cleared {deleted_expenses_count} expense(s) and {deleted_incomes_count} income(s) for {period_description} transactions."
    await query.edit_message_text(message_text, reply_markup=back_to_main_menu_keyboard(), parse_mode='HTML')
    
    db_session.close()
    return ConversationHandler.END

async def cancel_clear_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels the clear history operation."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Clear history operation cancelled. Returning to main menu.", reply_markup=back_to_main_menu_keyboard())
    return ConversationHandler.END
