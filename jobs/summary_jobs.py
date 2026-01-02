import datetime
import logging
import asyncio
import random

from telegram import Update, InputFile, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, ContextTypes

from models import SessionLocal, User
from services import SummaryService, UserService, SubscriptionService
from visuals import VisualsService
from services.subscription_service import MONTHLY_PRO_PRICE, YEARLY_PRO_PRICE, YEARLY_SAVINGS_NAIRA, YEARLY_SAVINGS_PERCENT


logger = logging.getLogger(__name__)

async def send_weekly_summaries_job(context: ContextTypes.DEFAULT_TYPE):
    logger.info("Running weekly summaries job...")
    application = context.application
    db_session = SessionLocal()
    summary_service = SummaryService(db_session)
    user_service = UserService(db_session)
    visuals_service = VisualsService()
    sub_service = SubscriptionService(db_session)

    users_to_process = summary_service.get_all_users_for_scheduled_summaries()

    for user in users_to_process:
        try:
            # Only send to Pro users
            if user.is_pro:
                summary_data = summary_service.get_weekly_summary(user.telegram_id)

                message_text = (
                    f"<b>📊 Your Weekly Summary ({user.first_name}):</b>\n\n"
                    f"💸 Total Expenses: ₦{summary_data['total_expenses']:,}\n"
                    f"📝 Expense Entries: {summary_data['num_expense_entries']}\n"
                    f"💰 Total Income: ₦{summary_data['total_income']:,}\n"
                    f"📈 Remaining Balance: ₦{summary_data['balance']:,}\n"
                    f"Budget Status: {summary_data['budget_status']}\n\n"
                )

                if summary_data['expenses_by_category']:
                    pie_chart_data = visuals_service.generate_pie_chart(
                        summary_data['expenses_by_category'],
                        title="This Week's Expenses by Category (Pie Chart)",
                        show_legend=True
                    )
                    donut_chart_data = visuals_service.generate_donut_chart(
                        summary_data['expenses_by_category'],
                        title="This Week's Expenses by Category (Donut Chart)",
                        show_legend=True
                    )
                    bar_chart_data = visuals_service.generate_bar_chart(
                        summary_data['expenses_by_category'],
                        title="Top 5 Categories This Week",
                        budget_line=None # Budget line to be implemented later
                    )
                    
                    await application.bot.send_message(
                        chat_id=user.telegram_id,
                        text=message_text,
                        parse_mode='HTML'
                    )

                    await application.bot.send_photo(
                        chat_id=user.telegram_id,
                        photo=InputFile(pie_chart_data),
                        caption="Here's your weekly expense breakdown (Pie Chart):"
                    )
                    await asyncio.sleep(0.5) # Short delay between sending charts

                    await application.bot.send_photo(
                        chat_id=user.telegram_id,
                        photo=InputFile(donut_chart_data),
                        caption="And here's another view (Donut Chart):"
                    )
                    await asyncio.sleep(0.5)

                    await application.bot.send_photo(
                        chat_id=user.telegram_id,
                        photo=InputFile(bar_chart_data),
                        caption="Top categories this week (Bar Chart):"
                    )
                    await asyncio.sleep(0.5)
                else:
                    await application.bot.send_message(
                        chat_id=user.telegram_id,
                        text=message_text + "\nNo expense data for this week to generate charts.",
                        parse_mode='HTML'
                    )
            
            await asyncio.sleep(random.uniform(1, 5)) # Staggered delivery
        except Exception as e:
            logger.error(f"Error sending weekly summary to user {user.telegram_id}: {e}")
    db_session.close()

async def send_monthly_summaries_job(context: ContextTypes.DEFAULT_TYPE):
    logger.info("Running monthly summaries job...")
    application = context.application
    db_session = SessionLocal()
    summary_service = SummaryService(db_session)
    user_service = UserService(db_session)
    visuals_service = VisualsService()
    sub_service = SubscriptionService(db_session)

    users_to_process = summary_service.get_all_users_for_scheduled_summaries()

    for user in users_to_process:
        try:
            summary_data = summary_service.get_monthly_summary(user.telegram_id)

            message_text = (
                f"<b>📊 Your Monthly Summary ({user.first_name}):</b>\n\n"
                f"💸 Total Expenses: ₦{summary_data['total_expenses']:,}\n"
                f"📝 Expense Entries: {summary_data['num_expense_entries']}\n"
                f"💰 Total Income: ₦{summary_data['total_income']:,}\n"
                f"📈 Remaining Balance: ₦{summary_data['balance']:,}\n"
                f"Budget Status: {summary_data['budget_status']}\n\n"
            )

            if summary_data['expenses_by_category']:
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
                    budget_line=None # Budget line to be implemented later
                )

                if not user.is_pro:
                    pie_chart_data = visuals_service.blur_image(pie_chart_data)
                    donut_chart_data = visuals_service.blur_image(donut_chart_data)
                    bar_chart_data = visuals_service.blur_image(bar_chart_data)
                    message_text += (
                        f"\n\n<i>Your spending patterns are blurred. Upgrade to Pro to see detailed charts!</i>\n\n"
                        f"<b>Upgrade to Pro:</b>\n"
                        f"Monthly: ₦{MONTHLY_PRO_PRICE:,}\n"
                        f"Yearly: ₦{YEARLY_PRO_PRICE:,} (Save ₦{YEARLY_SAVINGS_NAIRA:,} - {YEARLY_SAVINGS_PERCENT}%)"
                    )
                
                await application.bot.send_message(
                    chat_id=user.telegram_id,
                    text=message_text,
                    parse_mode='HTML'
                )

                await application.bot.send_photo(
                    chat_id=user.telegram_id,
                    photo=InputFile(pie_chart_data),
                    caption="Here's your monthly expense breakdown (Pie Chart):"
                )
                await asyncio.sleep(0.5)

                await application.bot.send_photo(
                    chat_id=user.telegram_id,
                    photo=InputFile(donut_chart_data),
                    caption="And here's another view (Donut Chart):"
                )
                await asyncio.sleep(0.5)

                await application.bot.send_photo(
                    chat_id=user.telegram_id,
                    photo=InputFile(bar_chart_data),
                    caption="Top categories this month (Bar Chart):"
                )
                await asyncio.sleep(0.5)
            else:
                await application.bot.send_message(
                    chat_id=user.telegram_id,
                    text=message_text + "\nNo expense data for this month to generate charts.",
                    parse_mode='HTML'
                )
            
            await asyncio.sleep(random.uniform(1, 5)) # Staggered delivery
        except Exception as e:
            logger.error(f"Error sending monthly summary to user {user.telegram_id}: {e}")
    db_session.close()
