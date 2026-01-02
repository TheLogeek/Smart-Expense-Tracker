import os
import logging
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, ContextTypes, CallbackQueryHandler,
    ConversationHandler, MessageHandler, filters
)
from models import create_all_tables, SessionLocal, add_default_categories, User
from services import UserService, ReminderService, ReferralService, ProfileService
from jobs import send_weekly_summaries_job, send_monthly_summaries_job, send_downgrade_notifications_job, send_expiry_reminders_job
from handlers import (
    main_menu_keyboard, back_to_main_menu_keyboard, summary_menu_keyboard, my_profile_menu_keyboard, upgrade_to_pro_menu_keyboard,
    start_expense_logging, enter_expense_details, select_category, add_custom_category, cancel,
    CHOOSING_LOG_TYPE, ENTER_EXPENSE_DETAILS, SELECT_CATEGORY, ADD_CUSTOM_CATEGORY, UPLOAD_RECEIPT,
    prompt_manual_entry, start_ocr_logging, upload_receipt,
    start_income_logging, enter_income_details, cancel_income,
    ENTER_INCOME_DETAILS,
    check_subscription_status, upgrade_confirm,
    generate_today_summary, generate_weekly_summary, generate_monthly_summary,
    start_set_budget, choose_budget_period, enter_budget_amount, choose_budget_category, cancel_budget_op,
    CHOOSE_BUDGET_PERIOD, ENTER_BUDGET_AMOUNT, CHOOSE_BUDGET_CATEGORY,
    toggle_daily_reminders_handler,
    generate_referral_link_handler,
    verify_payment_handler,
    start_create_profile, create_profile_type, create_profile_name,
    switch_profile_handler,
    CREATE_PROFILE_TYPE, ASK_PROFILE_NAME,
    features_handler, help_handler, export_logs_handler,
    transaction_history_handler, show_next_transactions, show_prev_transactions,
    VIEW_TRANSACTIONS, CLEAR_HISTORY_MENU, CONFIRM_CLEAR_HISTORY, # Add new states
    clear_history_menu_handler, execute_clear_history, cancel_clear_history # Add new handlers
)
import datetime
import zoneinfo
from zoneinfo import ZoneInfo
import json

# FastAPI imports
from fastapi import FastAPI, Request, BackgroundTasks, HTTPException, Response
import uvicorn

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Timezone for user-facing messages
AFRICA_LAGOS_TZ = ZoneInfo("Africa/Lagos")

# --- FastAPI App Initialization ---
app = FastAPI()

# Global variable to hold our python-telegram-bot Application instance
ptb_application: Application = None

# --- Telegram Bot Core Logic (from bot.py) ---
# Helper function to convert InlineKeyboardMarkup to a comparable format
def _serialize_reply_markup(markup: InlineKeyboardMarkup) -> str:
    if markup is None:
        return ""
    return json.dumps(markup.to_dict(), sort_keys=True)

async def send_reminders_job(context: ContextTypes.DEFAULT_TYPE):
    logger.info("Running daily reminders job...")
    application = context.application
    db_session = SessionLocal()
    reminder_service = ReminderService(db_session)
    
    users = db_session.query(User).filter(User.daily_reminders_enabled == True).all()
    for user in users:
        await reminder_service.send_daily_reminder(application, user.telegram_id)
    db_session.close()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    db_session = SessionLocal()
    user_service = UserService(db_session)
    profile_service = ProfileService(db_session)
    from services import SubscriptionService
    sub_service = SubscriptionService(db_session)

    telegram_user = update.effective_user
    referral_id = None
    
    if context.args and len(context.args) > 0 and context.args[0].startswith("paystack_verify_"):
        paystack_reference = context.args[0].replace("paystack_verify_", "")
        logger.info(f"Received Paystack deep link with reference: {paystack_reference}")
        
        verification_result = sub_service.handle_successful_payment(paystack_reference)
        
        if verification_result["status"]:
            await update.message.reply_html(
                f"🎉 Payment successful! {verification_result['message']}",
                reply_markup=main_menu_keyboard()
            )
            if 'paystack_reference' in context.user_data:
                del context.user_data['paystack_reference']
        else:
            await update.message.reply_html(
                f"❌ Payment verification failed: {verification_result['message']}\n\n"
                "If you believe this is an error, please try clicking the '✅ Verify Payment' button "
                "from your original payment message or contact support.",
                reply_markup=main_menu_keyboard()
            )
            context.user_data['paystack_reference'] = paystack_reference
        db_session.close()
        return ConversationHandler.END

    if context.args and len(context.args) > 0: 
        try:
            referral_id = int(context.args[0])
        except ValueError:
            logger.warning(f"Invalid referral ID received: {context.args[0]}")

    user = user_service.get_or_create_user(
        telegram_id=telegram_user.id,
        username=telegram_user.username,
        first_name=telegram_user.first_name,
        last_name=telegram_user.last_name,
        referral_id=referral_id,
        application=ptb_application # Pass the application instance
    )

    if not profile_service.get_profiles(user.telegram_id):
        return await start_create_profile(update, context)
    
    welcome_message = f"Hi {telegram_user.mention_html()}! Welcome to Smart Expense Tracker Bot.\n\n"

    current_profile = profile_service.get_current_profile(user.telegram_id)
    if current_profile:
        welcome_message += f"<b>Current Profile:</b> {current_profile.name} ({current_profile.profile_type})\n\n"

    if user.subscription_plan == "pro_trial":
        if user.trial_end_date:
            trial_end_date_lagos = user.trial_end_date.astimezone(AFRICA_LAGOS_TZ)
            welcome_message += (
                f"You have a Pro free trial until <b>{trial_end_date_lagos.strftime('%Y-%m-%d %H:%M:%S %Z%z')}</b>.\n\n"
            )
    elif user.is_pro:
        welcome_message += "You are currently a Pro user with unlimited access!\n\n"
    else:
        welcome_message += "You are currently a Free user. Log up to 150 expenses per month.\n\n"


    welcome_message += (
        "Here's how to log your expenses:\n"
        "Format 1: <code>paid [amount] for [description]</code> (e.g., <code>paid 5000 for fuel</code>)\n"
        "Format 2: <code>[amount] for [description]</code> (e.g., <code>5000 for fuel</code>)\n\n"
        "<b>OCR Receipt Logging</b> (Pro feature): Upload a receipt image, and I'll extract the details for you!\n\n"
        "What would you like to do?"
    )

    reply_markup = main_menu_keyboard()

    await update.message.reply_html(welcome_message, reply_markup=reply_markup)
    db_session.close()
    return ConversationHandler.END


async def button_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    current_text = query.message.text_html if query.message.text else None
    current_reply_markup_serialized = _serialize_reply_markup(query.message.reply_markup)
    
    new_text = None
    new_reply_markup = None

    if query.data == "main_menu":
        new_text = "Main Menu:"
        new_reply_markup = main_menu_keyboard()
    elif query.data == "cancel":
        new_text = "Operation cancelled."
        new_reply_markup = main_menu_keyboard()
    elif query.data == "generate_summary":
        new_text = "What summary would you like to generate?"
        new_reply_markup = summary_menu_keyboard()
    elif query.data == "my_profile":
        new_text = "My Profile:"
        new_reply_markup = my_profile_menu_keyboard()
    elif query.data == "upgrade_to_pro":
        new_text = "Upgrade to Pro:"
        new_reply_markup = upgrade_to_pro_menu_keyboard()
    elif query.data == "summary_today":
        await generate_today_summary(update, context)
        return
    elif query.data == "summary_this_week":
        await generate_weekly_summary(update, context)
        return
    elif query.data == "summary_this_month":
        await generate_monthly_summary(update, context)
        return
    elif query.data == "view_switch_profile":
        await switch_profile_handler(update, context)
        return
    elif query.data == "create_new_profile":
        await start_create_profile(update, context)
        return
    elif query.data == "features":
        await features_handler(update, context)
        return
    elif query.data == "help":
        await help_handler(update, context)
        return
    elif query.data == "export_logs":
        await export_logs_handler(update, context)
        return
    elif query.data == "transaction_history":
        await transaction_history_handler(update, context)
        return
    elif query.data.startswith("verify_payment_"):
        await verify_payment_handler(update, context)
        return
    elif query.data.startswith("switch_profile_"):
        db_session = SessionLocal()
        profile_service = ProfileService(db_session)
        user_telegram_id = update.effective_user.id
        profile_id = int(query.data.split('_')[-1])
        if profile_service.switch_profile(user_telegram_id, profile_id):
            new_current_profile = profile_service.get_profile_by_id(profile_id)
            new_text = f"Switched to profile: {new_current_profile.name} ({new_current_profile.profile_type})"
            new_reply_markup = back_to_main_menu_keyboard()
        else:
            new_text = "Failed to switch profile. Please try again."
            new_reply_markup = back_to_main_menu_keyboard()
        db_session.close()
    else:
        logger.warning(f"button_callback_handler caught unhandled data: {query.data}")
        new_text = "Unknown action. Returning to main menu."
        new_reply_markup = main_menu_keyboard()

    new_reply_markup_serialized = _serialize_reply_markup(new_reply_markup)

    if new_text and (new_text != current_text or new_reply_markup_serialized != current_reply_markup_serialized):
        if query.message.text:
            await query.edit_message_text(new_text, reply_markup=new_reply_markup, parse_mode='HTML')
        else:
            await context.bot.send_message(
                chat_id=update.effective_chat.id, text=new_text, reply_markup=new_reply_markup, parse_mode='HTML'
            )
            if query.message.reply_markup:
                await query.edit_message_reply_markup(reply_markup=None)

# --- FastAPI Lifecycle Events ---
@app.on_event("startup")
async def startup_event():
    logger.info("FastAPI app starting up. Initializing Telegram bot...")
    global ptb_application

    telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not telegram_bot_token:
        logger.error("TELEGRAM_BOT_TOKEN not found in environment variables.")
        raise ValueError("TELEGRAM_BOT_TOKEN is not set.")

    ptb_application = Application.builder().token(telegram_bot_token).build()
    await ptb_application.initialize() # Initialize the application


    # --- Register handlers ---
    # Unified Expense and OCR Conversation Handler
    expense_conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_expense_logging, pattern="^log_expense$"),
            CommandHandler("logexpense", start_expense_logging)
        ],
        states={
            CHOOSING_LOG_TYPE: [
                CallbackQueryHandler(prompt_manual_entry, pattern="^log_manual$"),
                CallbackQueryHandler(start_ocr_logging, pattern="^log_ocr$")
            ],
            ENTER_EXPENSE_DETAILS: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_expense_details)],
            UPLOAD_RECEIPT: [MessageHandler(filters.PHOTO, upload_receipt)],
            SELECT_CATEGORY: [CallbackQueryHandler(select_category, pattern="^category_.*$|^add_custom_category$")],
            ADD_CUSTOM_CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_custom_category)],
        },
        fallbacks=[CallbackQueryHandler(cancel, pattern="^cancel$"), CommandHandler("cancel", cancel)],
    )

    ptb_application.add_handler(expense_conv_handler)
    ptb_application.add_handler(ConversationHandler(
        entry_points=[CommandHandler("start", start), CallbackQueryHandler(start_create_profile, pattern="^create_new_profile$")],
        states={
            CREATE_PROFILE_TYPE: [CallbackQueryHandler(create_profile_type, pattern="^profile_type_.*$")],
            ASK_PROFILE_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_profile_name)],
        },
        fallbacks=[CallbackQueryHandler(cancel, pattern="^cancel$"), CommandHandler("cancel", cancel)],
    ))
    ptb_application.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(transaction_history_handler, pattern="^transaction_history$")],
        states={
            VIEW_TRANSACTIONS: [
                CallbackQueryHandler(show_next_transactions, pattern="^next_transactions$"),
                CallbackQueryHandler(show_prev_transactions, pattern="^prev_transactions$"),
                CallbackQueryHandler(clear_history_menu_handler, pattern="^clear_history_menu$"),
            ],
            CLEAR_HISTORY_MENU: [
                CallbackQueryHandler(execute_clear_history, pattern="^clear_today$|^clear_week$|^clear_month$|^clear_all$"),
                CallbackQueryHandler(transaction_history_handler, pattern="^transaction_history$"),
                CallbackQueryHandler(cancel_clear_history, pattern="^cancel$")
            ],
        },
        fallbacks=[CallbackQueryHandler(cancel, pattern="^cancel$"), CommandHandler("cancel", cancel)],
    ))
    ptb_application.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(start_income_logging, pattern="^log_income$")],
        states={ENTER_INCOME_DETAILS: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_income_details)]},
        fallbacks=[CallbackQueryHandler(cancel_income, pattern="^cancel$"), CommandHandler("cancel", cancel_income)],
    ))
    ptb_application.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(start_set_budget, pattern="^start_set_budget$")],
        states={
            CHOOSE_BUDGET_PERIOD: [CallbackQueryHandler(choose_budget_period, pattern="^budget_period_.*$")],
            ENTER_BUDGET_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_budget_amount)],
            CHOOSE_BUDGET_CATEGORY: [CallbackQueryHandler(choose_budget_category, pattern="^budget_category_.*$")],
        },
        fallbacks=[CallbackQueryHandler(cancel_budget_op, pattern="^cancel$"), CommandHandler("cancel", cancel_budget_op)],
    ))
    
    ptb_application.add_handler(CommandHandler("start", start)) # Moved here from conv handler entry points
    ptb_application.add_handler(CallbackQueryHandler(check_subscription_status, pattern="^check_subscription$"))
    ptb_application.add_handler(CallbackQueryHandler(upgrade_confirm, pattern="^upgrade_monthly$|^upgrade_yearly$"))
    ptb_application.add_handler(CallbackQueryHandler(toggle_daily_reminders_handler, pattern="^toggle_daily_reminders$"))
    ptb_application.add_handler(CallbackQueryHandler(generate_referral_link_handler, pattern="^refer_a_friend$"))
    ptb_application.add_handler(CallbackQueryHandler(verify_payment_handler, pattern="^verify_payment$"))
    ptb_application.add_handler(CallbackQueryHandler(switch_profile_handler, pattern="^view_switch_profile$"))
    ptb_application.add_handler(CallbackQueryHandler(button_callback_handler))

    # --- Job Queue Setup ---
    job_queue = ptb_application.job_queue
    job_queue.run_daily(send_reminders_job, time=datetime.time(hour=20, minute=0, tzinfo=AFRICA_LAGOS_TZ))
    job_queue.run_daily(send_weekly_summaries_job, time=datetime.time(hour=21, minute=0, tzinfo=AFRICA_LAGOS_TZ), days=(6,))
    job_queue.run_monthly(send_monthly_summaries_job, when=datetime.time(hour=22, minute=0, tzinfo=AFRICA_LAGOS_TZ), day=-1)
    job_queue.run_daily(send_downgrade_notifications_job, time=datetime.time(hour=23, minute=0, tzinfo=AFRICA_LAGOS_TZ))
    job_queue.run_daily(send_expiry_reminders_job, time=datetime.time(hour=9, minute=0, tzinfo=AFRICA_LAGOS_TZ))

    # --- Database Initialization ---
    create_all_tables()
    db_session = SessionLocal()
    add_default_categories(db_session)
    db_session.close()

    # --- Set Webhook ---
    webhook_url = os.getenv("WEBHOOK_URL") + "/webhook" # Assuming /webhook endpoint
    webhook_secret = os.getenv("WEBHOOK_SECRET") # Optional but recommended
    
    if not webhook_url:
        logger.error("WEBHOOK_URL not found in environment variables.")
        raise ValueError("WEBHOOK_URL is not set.")

    logger.info(f"Setting webhook to {webhook_url}")
    await ptb_application.bot.set_webhook(url=webhook_url, secret_token=webhook_secret)
    logger.info("Webhook set successfully.")
    
    # Start the PTB Application (without polling)
    await ptb_application.start()
    logger.info("PTB Application started (webhook mode).")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("FastAPI app shutting down. Stopping Telegram bot...")
    global ptb_application
    if ptb_application:
        await ptb_application.stop()
        await ptb_application.updater.stop() # Ensure updater is stopped
        await ptb_application.bot.delete_webhook()
        logger.info("PTB Application stopped and webhook deleted.")

# --- Webhook Endpoint ---
async def process_telegram_update(update_json: dict):
    """Processes a Telegram Update object in the background."""
    global ptb_application
    if ptb_application is None:
        logger.error("PTB Application not initialized.")
        return

    update = Update.de_json(update_json, ptb_application.bot)
    await ptb_application.process_update(update)

@app.post("/webhook")
async def webhook_receiver(request: Request, background_tasks: BackgroundTasks):
    # Telegram sends a POST request with the update data in the body
    update_json = await request.json()
    
    # Optional: Verify webhook secret
    webhook_secret = os.getenv("WEBHOOK_SECRET")
    if webhook_secret:
        if request.headers.get("X-Telegram-Bot-Api-Secret-Token") != webhook_secret:
            raise HTTPException(status_code=403, detail="Invalid webhook secret token")

    # Immediately return 200 OK
    background_tasks.add_task(process_telegram_update, update_json)
    return Response(status_code=200)

@app.get("/health")
async def health_check():
    return {"status": "ok"}

# To run this FastAPI app: uvicorn main_webhook:app --host 0.0.0.0 --port 8000
