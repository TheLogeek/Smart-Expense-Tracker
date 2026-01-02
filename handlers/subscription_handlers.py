from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from models import SessionLocal
from services import SubscriptionService, UserService, MONTHLY_PRO_PRICE, YEARLY_PRO_PRICE, YEARLY_SAVINGS_NAIRA, YEARLY_SAVINGS_PERCENT
from .menu_handlers import back_to_main_menu_keyboard
import logging
import re # Import re

logger = logging.getLogger(__name__)

async def check_subscription_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Checks and displays the user's current subscription status."""
    query = update.callback_query
    await query.answer()

    db_session = SessionLocal()
    sub_service = SubscriptionService(db_session)
    user_service = UserService(db_session)
    user_telegram_id = update.effective_user.id
    user = user_service.get_user(user_telegram_id)

    status = sub_service.get_user_subscription_status(user_telegram_id)

    message = f"<b>Your Current Plan:</b> {status['plan']}\n"
    if status['expires_at']:
        message += f"<b>Expires On:</b> {status['expires_at'].strftime('%Y-%m-%d %H:%M:%S %Z%z')}\n"
    
    message += "\n" + "Unlock unlimited features, OCR scanning, detailed analytics, and more with Pro!"

    keyboard = [
        [InlineKeyboardButton(f"Upgrade Monthly (₦{MONTHLY_PRO_PRICE:,})", callback_data="upgrade_monthly")],
        [InlineKeyboardButton(f"Upgrade Yearly (₦{YEARLY_PRO_PRICE:,})", callback_data="upgrade_yearly")],
        [InlineKeyboardButton("Back to Main Menu", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')
    db_session.close()
    return ConversationHandler.END # No conversation, just a response

async def upgrade_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Initiates the Paystack payment flow for the selected plan."""
    query = update.callback_query
    await query.answer("Initiating payment...")

    plan_type = query.data.split('_')[1] # 'monthly' or 'yearly'
    
    db_session = SessionLocal()
    user_service = UserService(db_session)
    sub_service = SubscriptionService(db_session)

    user_telegram_id = update.effective_user.id
    user = user_service.get_user(user_telegram_id)

    if not user:
        await query.edit_message_text("User not found. Please try /start again.", reply_markup=back_to_main_menu_keyboard())
        db_session.close()
        return ConversationHandler.END

    bot_username = context.bot.username # Get bot's username
    payment_init_response = sub_service.initiate_paystack_payment(user, plan_type, bot_username)

    if payment_init_response and payment_init_response["status"]:
        payment_link = payment_init_response["authorization_url"]
        reference = payment_init_response["reference"]
        # context.user_data['paystack_reference'] is no longer needed

        message = (
            f"You've chosen the {plan_type.capitalize()} Pro plan.\n"
            f"Please click the 'Pay Now' button below to complete your payment.\n"
            f"You will be redirected back to the bot after payment. "
            f"If your subscription doesn't update automatically, click the '✅ Verify Payment' button."
        )
        keyboard = [
            [InlineKeyboardButton("🔗 Pay Now", url=payment_link)],
            [InlineKeyboardButton("✅ Verify Payment", callback_data=f"verify_payment_{reference}")],
            [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup, disable_web_page_preview=True)
    else:
        message = (
            f"Failed to initiate payment for {plan_type.capitalize()} Pro plan. "
            f"Please try again later or contact support. Error: {payment_init_response.get('message', 'Unknown error')}. "
        )
        await query.edit_message_text(message, reply_markup=back_to_main_menu_keyboard())
    
    db_session.close()
    return ConversationHandler.END

async def verify_payment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Verifies a Paystack payment using the reference from callback_data."""
    query = update.callback_query
    await query.answer("Verifying payment...")

    # Extract reference directly from callback_data
    reference = query.data.replace("verify_payment_", "")
    user_telegram_id = update.effective_user.id

    if not reference:
        await query.edit_message_text(
            "No payment reference found in the button. Please try initiating the upgrade again.",
            reply_markup=back_to_main_menu_keyboard()
        )
        return ConversationHandler.END
    
    db_session = SessionLocal()
    sub_service = SubscriptionService(db_session)
    user_service = UserService(db_session)

    verification_result = sub_service.handle_successful_payment(reference)

    if verification_result["status"]:
        user = user_service.get_user(user_telegram_id) # Refresh user data
        await query.edit_message_text(
            f"🎉 Your Pro subscription is now active, {user.first_name}! Enjoy unlimited features.\n\n"
            f"<i>{verification_result['message']}</i>",
            reply_markup=back_to_main_menu_keyboard(),
            parse_mode='HTML'
        )
        logger.info(f"User {user_telegram_id} successfully upgraded to Pro via manual verification. Message: {verification_result['message']}")
    else:
        await query.edit_message_text(
            f"❌ Payment verification failed. {verification_result['message']}\n\n"
            "Please ensure you completed the payment and try again. If the issue persists, contact support.",
            reply_markup=back_to_main_menu_keyboard()
        )
        logger.warning(f"Payment verification failed for reference {reference} (user {user_telegram_id}). Message: {verification_result['message']}")
    
    # Clear the reference from user_data after an attempt
    if 'paystack_reference' in context.user_data:
        del context.user_data['paystack_reference']

    db_session.close()
    return ConversationHandler.END

async def cancel_subscription_op(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels the subscription operation."""
    query = update.callback_query
    if query:
        await query.answer()
        # if 'paystack_reference' in context.user_data: # No longer needed
        #    del context.user_data['paystack_reference'] 
        await query.edit_message_text("Subscription operation cancelled. Returning to main menu.", reply_markup=back_to_main_menu_keyboard())
    else:
        await update.message.reply_text("Subscription operation cancelled. Returning to main menu.", reply_markup=back_to_main_menu_keyboard())
    return ConversationHandler.END

# Removing the old paystack_callback_handler as its functionality is now covered by verify_payment_handler
# async def paystack_callback_handler(...):
#     pass