from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from services.subscription_service import MONTHLY_PRO_PRICE, YEARLY_PRO_PRICE, YEARLY_SAVINGS_NAIRA, YEARLY_SAVINGS_PERCENT

def main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("💸 Log Expense", callback_data="log_expense")],
        [InlineKeyboardButton("💰 Log Income", callback_data="log_income")],
        [InlineKeyboardButton("📊 Generate Summary", callback_data="generate_summary")],
        [InlineKeyboardButton("📜 Transaction History", callback_data="transaction_history")],
        [InlineKeyboardButton("👤 My Profile", callback_data="my_profile")],
        [InlineKeyboardButton("🎯 Set Budget", callback_data="start_set_budget")],
        [InlineKeyboardButton("📤 Export Logs (Pro)", callback_data="export_logs")],
        [InlineKeyboardButton("✨ Features", callback_data="features")],
        [InlineKeyboardButton("🚀 Upgrade to Pro", callback_data="upgrade_to_pro")],
        [InlineKeyboardButton("🤝 Refer a Friend", callback_data="refer_a_friend")],
        [InlineKeyboardButton("❓ Help", callback_data="help")],
        [InlineKeyboardButton("⏰ Manage Reminders", callback_data="manage_reminders")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel")],
    ]
    return InlineKeyboardMarkup(keyboard)

def my_profile_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("👀 View / Switch Profile", callback_data="view_switch_profile")],
        [InlineKeyboardButton("➕ Create New Profile", callback_data="create_new_profile")],
        [InlineKeyboardButton("💱 Change Currency", callback_data="change_currency")],
        [InlineKeyboardButton("💳 Check Current Subscription Plan", callback_data="check_subscription")],
        [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="main_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)

def upgrade_to_pro_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton(f"⬆️ Upgrade Monthly (₦{MONTHLY_PRO_PRICE:,})", callback_data="upgrade_monthly")],
        [InlineKeyboardButton(f"🌟 Upgrade Yearly (₦{YEARLY_PRO_PRICE:,})", callback_data="upgrade_yearly")],
        [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="main_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)

def summary_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("☀️ Today", callback_data="summary_today")],
        [InlineKeyboardButton("🗓️ This Week", callback_data="summary_this_week")],
        [InlineKeyboardButton("📅 This Month", callback_data="summary_this_month")],
        [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="main_menu")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel")],
    ]
    return InlineKeyboardMarkup(keyboard)

def back_to_main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="main_menu")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel")],
    ]
    return InlineKeyboardMarkup(keyboard)
