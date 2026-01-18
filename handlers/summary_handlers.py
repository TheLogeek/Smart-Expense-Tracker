from telegram import Update, InputFile
from telegram.ext import ContextTypes, ConversationHandler
from models import SessionLocal
from services import SummaryService, UserService, ProfileService, MONTHLY_PRO_PRICE, YEARLY_PRO_PRICE, YEARLY_SAVINGS_NAIRA, YEARLY_SAVINGS_PERCENT
from visuals import VisualsService
from utils.misc_utils import get_currency_symbol # Import get_currency_symbol
from .menu_handlers import back_to_main_menu_keyboard
import logging

logger = logging.getLogger(__name__)

async def generate_today_summary(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Generates and sends today's expense and income summary to the user."""
    query = update.callback_query
    await query.answer("Generating today's summary...")

    db_session = SessionLocal()
    summary_service = SummaryService(db_session)
    user_service = UserService(db_session)
    profile_service = ProfileService(db_session)
    visuals_service = VisualsService()

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

    current_profile = profile_service.get_current_profile(user_telegram_id)
    
    if not current_profile:
        await query.edit_message_text(
            "You need to select a profile first. Go to 'My Profile' -> 'View / Switch Profile' or 'Create New Profile'.",
            reply_markup=back_to_main_menu_keyboard()
        )
        db_session.close()
        return ConversationHandler.END
    
    currency_symbol = get_currency_symbol(current_profile.currency)

    summary_data = summary_service.get_daily_summary(current_profile.id)

    message_text = (
        f"<b>📊 Today's Summary ({current_profile.name}):</b>\n\n"
        f"💸 Total Expenses: {currency_symbol}{summary_data['total_expenses']:,}\n"
        f"📝 Expense Entries: {summary_data['num_expense_entries']}\n"
        f"💰 Total Income: {currency_symbol}{summary_data['total_income']:,}\n"
        f"📈 Remaining Balance: {currency_symbol}{summary_data['balance']:,}\n\n"
    )

    if summary_data["budget_insights"]:
        message_text += "<b>Budget Insights:</b>\n"
        for insight in summary_data["budget_insights"]:
            message_text += f"- {insight}\n"
        message_text += "\n"

    if summary_data['expenses_by_category']:
        # Extract overall budget amount if available for the bar chart
        overall_budget_amount = None
        for budget_status in summary_data.get('detailed_budget_statuses', []):
            if budget_status['is_overall_budget']:
                overall_budget_amount = budget_status['budget_amount']
                break

        pie_chart_data = visuals_service.generate_pie_chart(
            summary_data['expenses_by_category'],
            title="Today's Expenses by Category (Pie Chart)",
            show_legend=user.is_pro
        )
        donut_chart_data = visuals_service.generate_donut_chart(
            summary_data['expenses_by_category'],
            title="Today's Expenses by Category (Donut Chart)",
            show_legend=user.is_pro
        )
        bar_chart_data = visuals_service.generate_bar_chart(
            summary_data['expenses_by_category'],
            title="Top 5 Categories Today",
            overall_budget_amount=overall_budget_amount,
            total_expenses_for_period=summary_data['total_expenses']
        )

        if not user.is_pro:
            pie_chart_data = visuals_service.blur_image(pie_chart_data)
            donut_chart_data = visuals_service.blur_image(donut_chart_data)
            message_text += "\n\n<i>Your spending patterns are blurred. Upgrade to Pro to see detailed charts!</i>"
        
        # Send text summary
        await query.edit_message_text(message_text, parse_mode='HTML', reply_markup=back_to_main_menu_keyboard())

        # Send charts separately
        await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=InputFile(pie_chart_data),
            caption="Here's your daily expense breakdown (Pie Chart):",
            reply_markup=back_to_main_menu_keyboard()
        )
        await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=InputFile(donut_chart_data),
            caption="And here's another view (Donut Chart):",
            reply_markup=back_to_main_menu_keyboard()
        )
    else:
        await query.edit_message_text(
            message_text + "\n\nNo expense data for today to generate charts.",
            parse_mode='HTML',
            reply_markup=back_to_main_menu_keyboard()
        )

    db_session.close()
    return ConversationHandler.END


async def generate_weekly_summary(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Generates and sends this week's expense and income summary to the user."""
    query = update.callback_query
    await query.answer("Generating this week's summary...")

    db_session = SessionLocal()
    summary_service = SummaryService(db_session)
    user_service = UserService(db_session)
    profile_service = ProfileService(db_session)
    visuals_service = VisualsService()

    user_telegram_id = update.effective_user.id
    user = user_service.get_user(user_telegram_id)

    if not user:
        message = "It looks like you haven't started yet. Please use the /start command to begin!"
        if update.callback_query:
            await query.edit_message_text(message)
        else:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=message)
        db_session.close()
        return ConversationHandler.END

    current_profile = profile_service.get_current_profile(user_telegram_id)

    if not current_profile:
        await query.edit_message_text(
            "You need to select a profile first. Go to 'My Profile' -> 'View / Switch Profile' or 'Create New Profile'.",
            reply_markup=back_to_main_menu_keyboard()
        )
        db_session.close()
        return ConversationHandler.END
    
    currency_symbol = get_currency_symbol(current_profile.currency)

    summary_data = summary_service.get_weekly_summary(current_profile.id)

    message_text = (
        f"<b>📊 This Week's Summary ({current_profile.name}):</b>\n\n"
        f"💸 Total Expenses: {currency_symbol}{summary_data['total_expenses']:,}\n"
        f"📝 Expense Entries: {summary_data['num_expense_entries']}\n"
        f"💰 Total Income: {currency_symbol}{summary_data['total_income']:,}\n"
        f"📈 Remaining Balance: {currency_symbol}{summary_data['balance']:,}\n\n"
    )

    if summary_data["budget_insights"]:
        message_text += "<b>Budget Insights:</b>\n"
        for insight in summary_data["budget_insights"]:
            message_text += f"- {insight}\n"
        message_text += "\n"

    if summary_data['expenses_by_category']:
        # Extract overall budget amount if available for the bar chart
        overall_budget_amount = None
        for budget_status in summary_data.get('detailed_budget_statuses', []):
            if budget_status['is_overall_budget']:
                overall_budget_amount = budget_status['budget_amount']
                break

        pie_chart_data = visuals_service.generate_pie_chart(
            summary_data['expenses_by_category'],
            title="This Week's Expenses by Category (Pie Chart)",
            show_legend=user.is_pro
        )
        donut_chart_data = visuals_service.generate_donut_chart(
            summary_data['expenses_by_category'],
            title="This Week's Expenses by Category (Donut Chart)",
            show_legend=user.is_pro
        )
        bar_chart_data = visuals_service.generate_bar_chart(
            summary_data['expenses_by_category'],
            title="Top 5 Categories This Week",
            overall_budget_amount=overall_budget_amount,
            total_expenses_for_period=summary_data['total_expenses']
        )

        if not user.is_pro:
            pie_chart_data = visuals_service.blur_image(pie_chart_data)
            donut_chart_data = visuals_service.blur_image(donut_chart_data)
            bar_chart_data = visuals_service.blur_image(bar_chart_data)
            message_text += "\n\n<i>Your spending patterns are blurred. Upgrade to Pro to see detailed charts!</i>"
        
        # Send text summary
        await query.edit_message_text(message_text, parse_mode='HTML', reply_markup=back_to_main_menu_keyboard())

        # Send charts separately
        await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=InputFile(pie_chart_data),
            caption="Here's your weekly expense breakdown (Pie Chart):",
            reply_markup=back_to_main_menu_keyboard()
        )
        await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=InputFile(donut_chart_data),
            caption="And here's another view (Donut Chart):",
            reply_markup=back_to_main_menu_keyboard()
        )
        await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=InputFile(bar_chart_data),
            caption="Top categories this week (Bar Chart):",
            reply_markup=back_to_main_menu_keyboard()
        )
    else:
        await query.edit_message_text(
            message_text + "\n\nNo expense data for this week to generate charts.",
            parse_mode='HTML',
            reply_markup=back_to_main_menu_keyboard()
        )

    db_session.close()
    return ConversationHandler.END


async def generate_monthly_summary(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Generates and sends this month's expense and income summary to the user."""
    query = update.callback_query
    await query.answer("Generating this month's summary...")

    db_session = SessionLocal()
    summary_service = SummaryService(db_session)
    user_service = UserService(db_session)
    profile_service = ProfileService(db_session)
    visuals_service = VisualsService()

    user_telegram_id = update.effective_user.id
    user = user_service.get_user(user_telegram_id)

    if not user:
        message = "It looks like you haven't started yet. Please use the /start command to begin!"
        if update.callback_query:
            await query.edit_message_text(message)
        else:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=message)
        db_session.close()
        return ConversationHandler.END

    current_profile = profile_service.get_current_profile(user_telegram_id)

    if not current_profile:
        await query.edit_message_text(
            "You need to select a profile first. Go to 'My Profile' -> 'View / Switch Profile' or 'Create New Profile'.",
            reply_markup=back_to_main_menu_keyboard()
        )
        db_session.close()
        return ConversationHandler.END
    
    currency_symbol = get_currency_symbol(current_profile.currency)

    summary_data = summary_service.get_monthly_summary(current_profile.id)

    message_text = (
        f"<b>📊 This Month's Summary ({current_profile.name}):</b>\n\n"
        f"💸 Total Expenses: {currency_symbol}{summary_data['total_expenses']:,}\n"
        f"📝 Expense Entries: {summary_data['num_expense_entries']}\n"
        f"💰 Total Income: {currency_symbol}{summary_data['total_income']:,}\n"
        f"📈 Remaining Balance: {currency_symbol}{summary_data['balance']:,}\n\n"
    )

    if summary_data["budget_insights"]:
        message_text += "<b>Budget Insights:</b>\n"
        for insight in summary_data["budget_insights"]:
            message_text += f"- {insight}\n"
        message_text += "\n"

    if summary_data['expenses_by_category']:
        # Extract overall budget amount if available for the bar chart
        overall_budget_amount = None
        for budget_status in summary_data.get('detailed_budget_statuses', []):
            if budget_status['is_overall_budget']:
                overall_budget_amount = budget_status['budget_amount']
                break

        pie_chart_data = visuals_service.generate_pie_chart(
            summary_data['expenses_by_category'],
            title="This Month's Expenses by Category (Pie Chart)",
            show_legend=user.is_pro
        )
        donut_chart_data = visuals_service.generate_donut_chart(
            summary_data['expenses_by_category'],
            title="This Month's Expenses by Category (Donut Chart)",
            show_legend=user.is_pro
        )
        bar_chart_data = visuals_service.generate_bar_chart(
            summary_data['expenses_by_category'],
            title="Top 5 Categories This Month",
            overall_budget_amount=overall_budget_amount,
            total_expenses_for_period=summary_data['total_expenses']
        )

        if not user.is_pro:
            pie_chart_data = visuals_service.blur_image(pie_chart_data)
            donut_chart_data = visuals_service.blur_image(donut_chart_data)
            bar_chart_data = visuals_service.blur_image(bar_chart_data)
            message_text += (
                f"\n\n<i>Your spending patterns are blurred. Upgrade to Pro to see detailed charts!</i>\n\n"
                f"<b>Upgrade to Pro:</b>\n"
                f"Monthly: {currency_symbol}{MONTHLY_PRO_PRICE:,}\n"
                f"Yearly: {currency_symbol}{YEARLY_PRO_PRICE:,} (Save {currency_symbol}{YEARLY_SAVINGS_NAIRA:,} - {YEARLY_SAVINGS_PERCENT}%)"
            )
        
        # Send text summary
        await query.edit_message_text(message_text, parse_mode='HTML', reply_markup=back_to_main_menu_keyboard())

        # Send charts separately
        await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=InputFile(pie_chart_data),
            caption="Here's your monthly expense breakdown (Pie Chart):",
            reply_markup=back_to_main_menu_keyboard()
        )
        await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=InputFile(donut_chart_data),
            caption="And here's another view (Donut Chart):",
            reply_markup=back_to_main_menu_keyboard()
        )
        await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=InputFile(bar_chart_data),
            caption="Top categories this month (Bar Chart):",
            reply_markup=back_to_main_menu_keyboard()
        )
    else:
        await query.edit_message_text(
            message_text + "\n\nNo expense data for this month to generate charts.",
            parse_mode='HTML',
            reply_markup=back_to_main_menu_keyboard()
        )

    db_session.close()
    return ConversationHandler.END
