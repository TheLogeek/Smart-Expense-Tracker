from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from models import SessionLocal
from services import ExpenseService, UserService, SubscriptionService, ProfileService, OCRService
from utils.misc_utils import get_currency_symbol # Import get_currency_symbol
from .menu_handlers import back_to_main_menu_keyboard
import logging
import io
import json
import re
import datetime
import PIL.Image
from telegram.error import BadRequest

logger = logging.getLogger(__name__)

# States for expense logging conversation
CHOOSING_LOG_TYPE, ENTER_EXPENSE_DETAILS, SELECT_CATEGORY, ADD_CUSTOM_CATEGORY, UPLOAD_RECEIPT = range(5)

async def start_expense_logging(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the expense logging conversation by asking for the log type."""
    logger.info("start_expense_logging entered.")
    
    # Create a new session for this conversation and store it in context
    db_session = SessionLocal()
    context.user_data['db_session'] = db_session

    user_service = UserService(db_session)
    expense_service = ExpenseService(db_session)
    profile_service = ProfileService(db_session)
    
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
        logger.info(f"start_expense_logging returning ConversationHandler.END for user {user_telegram_id} (no user)")
        return ConversationHandler.END

    current_profile = profile_service.get_current_profile(user.telegram_id)
    if not current_profile:
        message = "You need to select a profile first. Go to 'My Profile' -> 'View / Switch Profile' or 'Create New Profile'."
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.edit_message_text(message, reply_markup=back_to_main_menu_keyboard())
        else:
            await update.message.reply_text(message, reply_markup=back_to_main_menu_keyboard())
        db_session.close()
        logger.info(f"start_expense_logging returning ConversationHandler.END for user {user_telegram_id} (no profile)")
        return ConversationHandler.END

    if not expense_service.can_log_expense(user):
        monthly_count = expense_service.get_monthly_expense_count(current_profile.id)
        reset_date = expense_service.get_monthly_limit_reset_date()
        message = (
            f"You have reached your monthly limit of 150 expenses for this profile ({monthly_count} logged).\n"
            f"Please upgrade to Pro for unlimited expense logging or wait until "
            f"<b>{reset_date.strftime('%b %d, %Y')}</b> when your limit resets."
        )
        keyboard = [
            [InlineKeyboardButton("🚀 Upgrade to Pro", callback_data="upgrade_to_pro")],
            [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')
        else:
            await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='HTML')
        db_session.close()
        logger.info(f"start_expense_logging returning ConversationHandler.END for user {user_telegram_id} (expense limit)")
        return ConversationHandler.END

    keyboard = [
        [InlineKeyboardButton("✍️ Type it Out", callback_data="log_manual")],
        [InlineKeyboardButton("📷 Scan Receipt (OCR)", callback_data="log_ocr")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message_text = "How would you like to log this expense?"
    if update.callback_query:
        await update.callback_query.edit_message_text(message_text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(message_text, reply_markup=reply_markup)

    logger.info("start_expense_logging returning CHOOSING_LOG_TYPE")
    return CHOOSING_LOG_TYPE

async def prompt_manual_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Prompts the user to manually enter expense details."""
    logger.info(f"prompt_manual_entry entered for user {update.effective_user.id}")
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "Please enter your expense details. E.g., 'paid 5000 for fuel' or '1200 for groceries'.",
        reply_markup=back_to_main_menu_keyboard()
    )
    logger.info("prompt_manual_entry returning ENTER_EXPENSE_DETAILS")
    return ENTER_EXPENSE_DETAILS

async def start_ocr_logging(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Prompts the user to upload a receipt for OCR."""
    logger.info(f"start_ocr_logging entered for user {update.effective_user.id}")
    query = update.callback_query
    await query.answer()
    
    db_session = context.user_data['db_session'] # Retrieve session
    user_service = UserService(db_session)
    user = user_service.get_user(update.effective_user.id)

    if not user or not user.is_pro:
        await query.edit_message_text("OCR receipt logging is a Pro feature. Please upgrade your plan.", reply_markup=back_to_main_menu_keyboard())
        db_session.close()
        logger.info(f"start_ocr_logging returning ConversationHandler.END for user {user.telegram_id} (not Pro)")
        return ConversationHandler.END

    await query.edit_message_text("Please upload a receipt image for OCR processing.", reply_markup=back_to_main_menu_keyboard())
    logger.info("start_ocr_logging returning UPLOAD_RECEIPT")
    return UPLOAD_RECEIPT

async def enter_expense_details(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Parses manually entered expense details and asks for category."""
    logger.info(f"enter_expense_details entered for user {update.effective_user.id} with text: {update.message.text}")
    text = update.message.text
    db_session = context.user_data['db_session'] # Retrieve session
    expense_service = ExpenseService(db_session)
    profile_service = ProfileService(db_session)
    
    user_telegram_id = update.effective_user.id
    current_profile = profile_service.get_current_profile(user_telegram_id)

    amount, description = expense_service.parse_expense_message(text)
    logger.info(f"Parsed amount: {amount}, description: {description}")
    
    if amount is None or description is None:
        await update.message.reply_text(
            "I couldn't understand that format. Please try again.",
            reply_markup=back_to_main_menu_keyboard()
        )
        logger.info(f"enter_expense_details returning ENTER_EXPENSE_DETAILS (retry) for user {user_telegram_id} (parse failed)")
        return ENTER_EXPENSE_DETAILS

    context.user_data['expense_amount'] = amount
    context.user_data['expense_description'] = description
    context.user_data['expense_date'] = None # Manual entry uses current date by default in service

    categories = expense_service.get_categories(current_profile.id)
    keyboard = []
    for category in categories:
        keyboard.append([InlineKeyboardButton(category.name, callback_data=f"category_{category.id}")])
    keyboard.append([InlineKeyboardButton("Add Custom Category", callback_data="add_custom_category")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    currency_symbol = get_currency_symbol(current_profile.currency)

    await update.message.reply_text(
        f"You entered: \nAmount: {currency_symbol}{amount:,}\nDescription: {description}\n\nPlease select a category:",
        reply_markup=reply_markup
    )
    logger.info(f"enter_expense_details returning SELECT_CATEGORY for user {user_telegram_id}")
    return SELECT_CATEGORY

async def upload_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles the uploaded receipt image and performs OCR."""
    logger.info(f"upload_receipt entered for user {update.effective_user.id}")
    if not update.message.photo:
        await update.message.reply_text(
            "That doesn't look like an image. Please upload a receipt photo.",
            reply_markup=back_to_main_menu_keyboard()
        )
        logger.info(f"upload_receipt returning UPLOAD_RECEIPT (not photo) for user {update.effective_user.id}")
        return UPLOAD_RECEIPT

    photo_file = await update.message.photo[-1].get_file()
    image_bytes = await photo_file.download_as_bytearray()
    logger.info(f"Image received, size: {len(image_bytes)} bytes")

    ocr_service = OCRService()
    ocr_result_text = await ocr_service.process_image_with_gemini_ocr(io.BytesIO(image_bytes))
    logger.info(f"OCR raw text response: {ocr_result_text}")

    if ocr_result_text.startswith("Error:") or "image is not a valid receipt" in ocr_result_text.lower():
        await update.message.reply_text(
            f"Failed to process image: {ocr_result_text}. Please try again or log manually.",
            reply_markup=back_to_main_menu_keyboard()
        )
        context.user_data['db_session'].close()
        return ConversationHandler.END
    
    # Use the existing expense parser on the OCR text
    db_session = context.user_data['db_session']
    expense_service = ExpenseService(db_session)
    
    profile_service = ProfileService(db_session) # Fetch profile service
    user_telegram_id = update.effective_user.id
    current_profile = profile_service.get_current_profile(user_telegram_id) # Get current profile

    amount, description = expense_service.parse_expense_message(ocr_result_text)
    
    if amount is None:
        await update.message.reply_text(
            f"OCR processed the image, but I couldn't understand the amount or format.\n\n"
            f"Result: `{ocr_result_text}`\n\n"
            f"Please try another image or log manually.",
            reply_markup=back_to_main_menu_keyboard(),
            parse_mode='Markdown'
        )
        context.user_data['db_session'].close()
        return ConversationHandler.END

    context.user_data['expense_amount'] = amount
    context.user_data['expense_description'] = description
    context.user_data['expense_date'] = None # OCR doesn't provide a date with this prompt

    
    categories = expense_service.get_categories(current_profile.id)
    
    keyboard = []
    for category in categories:
        keyboard.append([InlineKeyboardButton(category.name, callback_data=f"category_{category.id}")])
    keyboard.append([InlineKeyboardButton("Add Custom Category", callback_data="add_custom_category")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    
    currency_symbol = get_currency_symbol(current_profile.currency) # Get currency symbol

    await update.message.reply_text(
        f"OCR results:\nAmount: {currency_symbol}{amount:,}\nDescription: {description}\n\n"
        f"Please select a category or add a new one:",
        reply_markup=reply_markup
    )
    logger.info("upload_receipt returning SELECT_CATEGORY")
    return SELECT_CATEGORY

async def select_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles category selection for both manual and OCR expenses."""
    logger.info(f"select_category entered for user {update.effective_user.id} with query.data: {update.callback_query.data}")
    query = update.callback_query
    await query.answer()

    db_session = context.user_data['db_session'] # Retrieve session
    expense_service = ExpenseService(db_session)
    profile_service = ProfileService(db_session)
    
    user_telegram_id = update.effective_user.id
    current_profile = profile_service.get_current_profile(user_telegram_id)

    if query.data == "add_custom_category":
        await query.edit_message_text(
            "Please enter the name for your new custom category.",
            reply_markup=back_to_main_menu_keyboard()
        )
        logger.info("select_category returning ADD_CUSTOM_CATEGORY")
        return ADD_CUSTOM_CATEGORY
    elif query.data.startswith("category_"):
        category_id = int(query.data.split('_')[1])
        
        category = expense_service.get_category_by_id(category_id)
        
        if not category:
            await query.edit_message_text("Selected category not found. Please try again.", reply_markup=back_to_main_menu_keyboard())
            logger.info("select_category returning SELECT_CATEGORY (category not found)")
            return SELECT_CATEGORY

        context.user_data['expense_category_id'] = category_id
        
        amount = context.user_data['expense_amount']
        description = context.user_data['expense_description']
        expense_date = context.user_data.get('expense_date')

        expense_service.add_expense(
            profile_id=current_profile.id,
            amount=amount,
            description=description,
            category_id=category_id,
            date=expense_date
        )
        
        currency_symbol = get_currency_symbol(current_profile.currency) # Get currency symbol
        await query.edit_message_text(
            f"Expense of {currency_symbol}{amount:,} for {description} under '{category.name}' saved successfully!",
            reply_markup=back_to_main_menu_keyboard()
        )
        db_session.close() # Close session on conversation end
        logger.info("select_category returning ConversationHandler.END (expense saved)")
        return ConversationHandler.END
    
    await query.edit_message_text("Invalid selection. Please try again.", reply_markup=back_to_main_menu_keyboard())
    logger.info("select_category returning SELECT_CATEGORY (invalid selection)")
    return ConversationHandler.END

async def add_custom_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Adds a new custom category and saves the expense."""
    logger.info(f"add_custom_category entered for user {update.effective_user.id} with text: {update.message.text}")
    category_name = update.message.text.strip()
    db_session = context.user_data['db_session'] # Retrieve session
    expense_service = ExpenseService(db_session)
    profile_service = ProfileService(db_session)
    user_telegram_id = update.effective_user.id
    current_profile = profile_service.get_current_profile(user_telegram_id)

    result = expense_service.add_custom_category(current_profile.id, category_name)

    if isinstance(result, str): # expense_service returned an error or limit message
        message_to_user = result
        if "Free users are limited" in result:
            keyboard = [
                [InlineKeyboardButton("🚀 Upgrade to Pro", callback_data="upgrade_to_pro")],
                [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="main_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
        else:
            reply_markup = back_to_main_menu_keyboard()
        
        await update.message.reply_text(
            message_to_user,
            reply_markup=reply_markup,
            parse_mode='HTML' if "Free users are limited" in result else None
        )
        logger.info(f"add_custom_category returning ADD_CUSTOM_CATEGORY (error/limit) for user {user_telegram_id}")
        return ADD_CUSTOM_CATEGORY # Stay in this state to allow another attempt or cancel
    
    # If not a string, it means a new Category object was returned
    new_category = result
    
    context.user_data['expense_category_id'] = new_category.id

    amount = context.user_data['expense_amount']
    description = context.user_data['expense_description']
    expense_date = context.user_data.get('expense_date')
    
    expense_service.add_expense(
        profile_id=current_profile.id,
        amount=amount,
        description=description,
        category_id=new_category.id,
        date=expense_date
    )
    currency_symbol = get_currency_symbol(current_profile.currency) # Get currency symbol

    await update.message.reply_text(
        f"Custom category '{new_category.name}' added and expense of {currency_symbol}{amount:,} for {description} saved successfully!",
        reply_markup=back_to_main_menu_keyboard()
    )
    db_session.close() # Close session on conversation end
    logger.info("add_custom_category returning ConversationHandler.END (custom category added, expense saved)")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels the current conversation."""
    logger.info(f"cancel handler entered for user {update.effective_user.id}")
    query = update.callback_query
    if query:
        try:
            await query.answer()
        except BadRequest:
            logger.warning("Query is too old to answer in cancel handler.")
        
        new_text = "Operation cancelled. Returning to main menu."
        
        # Safely attempt to edit the message, or send a new one.
        try:
            if query.message.text != new_text:
                await query.edit_message_text(new_text, reply_markup=back_to_main_menu_keyboard())
            # If the text is the same, no action is needed, but we still end the conversation.
        except BadRequest as e:
            # This can happen if the message is a photo with no text caption to edit.
            logger.warning(f"BadRequest on edit_message_text in cancel: {e}. Sending new message.")
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=new_text,
                reply_markup=back_to_main_menu_keyboard()
            )
            # Clean up the old message's keyboard if it was from a photo
            if query.message.reply_markup:
                try:
                    await query.edit_message_reply_markup(reply_markup=None)
                except BadRequest as e_markup:
                    logger.warning(f"Failed to remove reply markup from original message: {e_markup}")

    else: # If it's a command like /cancel
        await update.message.reply_text("Operation cancelled. Returning to main menu.", reply_markup=back_to_main_menu_keyboard())
    
    # Ensure session is closed on cancel
    if 'db_session' in context.user_data and context.user_data['db_session'] is not None:
        context.user_data['db_session'].close()
        logger.info(f"DB session closed during cancel for user {update.effective_user.id}")
        context.user_data['db_session'] = None # Clear it

    logger.info(f"cancel handler returning ConversationHandler.END for user {update.effective_user.id}")
    return ConversationHandler.END
