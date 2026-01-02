import datetime
import logging
from telegram.ext import ContextTypes
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from models import SessionLocal, User # Import User for querying
from services import SubscriptionService
from handlers.menu_handlers import upgrade_to_pro_menu_keyboard # Reusing the upgrade keyboard

logger = logging.getLogger(__name__)

async def send_expiry_reminders_job(context: ContextTypes.DEFAULT_TYPE):
    """
    Job to send reminders to users whose subscription (trial or paid)
    is expiring within the next 24 hours.
    """
    logger.info("Running subscription expiry reminders job...")
    application = context.application
    db_session = SessionLocal()
    sub_service = SubscriptionService(db_session)

    expiring_users = sub_service.get_users_with_expiring_subscriptions()

    for user in expiring_users:
        if user.subscription_plan == "pro_trial" and user.trial_end_date:
            expiry_date_local = user.trial_end_date.astimezone(sub_service.AFRICA_LAGOS_TZ)
            plan_type = "Pro trial"
        elif user.subscription_plan == "pro_paid" and user.subscription_end_date:
            expiry_date_local = user.subscription_end_date.astimezone(sub_service.AFRICA_LAGOS_TZ)
            plan_type = "Pro"
        else:
            continue # Should not happen if query is correct

        message = (
            f"🔔 Your {plan_type} subscription is ending soon!\n\n"
            f"It will expire tomorrow, <b>{expiry_date_local.strftime('%Y-%m-%d %H:%M %Z%z')}</b>.\n"
            "Don't miss out on unlimited features and detailed insights!\n\n"
            "Upgrade now to continue enjoying uninterrupted service."
        )
        
        try:
            await application.bot.send_message(
                chat_id=user.telegram_id,
                text=message,
                reply_markup=upgrade_to_pro_menu_keyboard(),
                parse_mode='HTML'
            )
            logger.info(f"Subscription expiry reminder sent to user {user.telegram_id}")
        except Exception as e:
            logger.error(f"Failed to send expiry reminder to user {user.telegram_id}: {e}")
    
    db_session.close()

async def send_downgrade_notifications_job(context: ContextTypes.DEFAULT_TYPE):
    """
    Job to downgrade users with expired subscriptions and notify them.
    """
    logger.info("Running subscription downgrade notifications job...")
    application = context.application
    db_session = SessionLocal()
    sub_service = SubscriptionService(db_session)

    downgraded_user_ids = sub_service.downgrade_expired_subscriptions()

    for user_telegram_id in downgraded_user_ids:
        message = (
            "⚠️ Your Pro subscription has ended.\n\n"
            "You have been successfully downgraded to the Free plan. "
            "You can still log up to 150 expenses per month.\n\n"
            "Upgrade to Pro anytime to unlock all features!"
        )
        try:
            await application.bot.send_message(
                chat_id=user_telegram_id,
                text=message,
                reply_markup=upgrade_to_pro_menu_keyboard(),
                parse_mode='HTML'
            )
            logger.info(f"Downgrade notification sent to user {user_telegram_id}")
        except Exception as e:
            logger.error(f"Failed to send downgrade notification to user {user_telegram_id}: {e}")
    
    db_session.close()