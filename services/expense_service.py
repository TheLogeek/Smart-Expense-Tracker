import logging
from sqlalchemy.orm import Session
from models import Expense, Category, User
import datetime # Keep base datetime for utcnow
from datetime import timezone # Import timezone
import re
from sqlalchemy import func, delete # Import delete
from utils.datetime_utils import wat_month_bounds_utc, to_wat, WAT # Import the new utilities
# Removed: from services import UserService, ProfileService # Moved inside function to break circular import

FREE_CUSTOM_CATEGORY_LIMIT = 3

class ExpenseService:
    def __init__(self, db_session: Session):
        self.db_session = db_session

    def add_expense(self, profile_id: int, amount: float, description: str, category_id: int = None, date: datetime = None):
        expense = Expense(
            profile_id=profile_id,
            amount=amount,
            description=description,
            category_id=category_id,
            date=date if date is not None else datetime.datetime.now(timezone.utc) # Use provided date or fallback to now
        )
        self.db_session.add(expense)
        self.db_session.commit()
        self.db_session.refresh(expense)
        return expense

    def parse_expense_message(self, message_text: str):
        # Regex to match "paid [amount] for [description]" or "[amount] for [description]"
        pattern = re.compile(r"(?:paid\s+)?(\d+(?:[.,]\d{1,2})?)\s+for\s+(.+)", re.IGNORECASE)
        match = pattern.match(message_text.strip())
        if match:
            amount_str = match.group(1).replace(',', '.') # Handle comma as decimal separator
            amount = float(amount_str)
            description = match.group(2).strip()
            return amount, description
        return None, None
    
    def get_categories(self, profile_id: int):
        # Get default categories (profile_id is NULL)
        default_categories = self.db_session.query(Category).filter(Category.profile_id == None).all()
        # Get custom categories for the profile
        user_categories = self.db_session.query(Category).filter(Category.profile_id == profile_id).all()
        return default_categories + user_categories

    def add_custom_category(self, profile_id: int, category_name: str):
        # Local imports to break circular dependency
        from services import UserService, ProfileService 

        user_service = UserService(self.db_session)
        profile_service = ProfileService(self.db_session)
        
        current_profile = profile_service.get_profile_by_id(profile_id)
        if not current_profile:
            return "Profile not found."

        user = user_service.get_user(current_profile.user_id) # user_id on Profile is telegram_id
        if not user:
            return "User not found."

        # Restrict free users
        if not user.is_pro:
            custom_categories_count = self.db_session.query(Category).filter(
                Category.profile_id == profile_id
            ).count()
            if custom_categories_count >= FREE_CUSTOM_CATEGORY_LIMIT:
                return f"Free users are limited to {FREE_CUSTOM_CATEGORY_LIMIT} custom categories. Please upgrade to Pro to create more!"

        # Check for duplicates (case-insensitive) for the profile or in default categories
        existing_category = self.db_session.query(Category).filter(
            (Category.profile_id == profile_id) | (Category.profile_id == None),
            Category.name.ilike(category_name)
        ).first()

        if existing_category:
            return "Category already exists."

        new_category = Category(name=category_name, profile_id=profile_id)
        self.db_session.add(new_category)
        self.db_session.commit()
        self.db_session.refresh(new_category)
        return new_category

    def get_category_by_id(self, category_id: int):
        return self.db_session.query(Category).filter(Category.id == category_id).first()

    def get_monthly_expense_count(self, profile_id: int) -> int:
        start_of_month_utc, start_of_next_month_utc = wat_month_bounds_utc()
        
        count = self.db_session.query(func.count(Expense.id)).filter(
            Expense.profile_id == profile_id,
            Expense.date >= start_of_month_utc,
            Expense.date < start_of_next_month_utc
        ).scalar()
        return count

    def get_monthly_limit_reset_date(self) -> datetime.datetime:
        # Get the start of the current WAT month in UTC
        start_this_month_utc, _ = wat_month_bounds_utc()
        # Convert it to WAT to do the month calculation, then back to UTC for the result
        start_this_month_wat = to_wat(start_this_month_utc)
        
        # Calculate start of next month in WAT
        if start_this_month_wat.month == 12:
            reset_date_wat = start_this_month_wat.replace(year=start_this_month_wat.year + 1, month=1, day=1)
        else:
            reset_date_wat = start_this_month_wat.replace(month=start_this_month_wat.month + 1, day=1)
            
        return reset_date_wat # Return WAT-aware datetime for display, consistent with trial_end_date.

    def can_log_expense(self, user: User) -> bool:
        if user.is_pro:
            return True
        
        # Free users can only have one profile, so we can use the first one
        if not user.profiles:
            return False # Should not happen if profile is created on start
            
        profile = user.profiles[0]
        monthly_expense_count = self.get_monthly_expense_count(profile.id)
        return monthly_expense_count < 150 # Free user limit

    def get_expenses_by_profile(self, profile_id: int):
        expenses = self.db_session.query(Expense).filter(Expense.profile_id == profile_id).order_by(Expense.date).all()
        for exp in expenses:
            if exp.date and exp.date.tzinfo is None:
                exp.date = exp.date.replace(tzinfo=timezone.utc) # Assume naive is UTC
            logging.info(f"Expense ID: {exp.id}, Date: {exp.date}, TZInfo: {exp.date.tzinfo}, Type: {type(exp.date)}")
        return expenses

    def delete_expenses_by_date_range(self, profile_id: int, start_date_utc: datetime.datetime, end_date_utc: datetime.datetime) -> int:
        """Deletes expenses for a given profile within a specified UTC date range."""
        deleted_count = self.db_session.query(Expense).filter(
            Expense.profile_id == profile_id,
            Expense.date >= start_date_utc,
            Expense.date < end_date_utc
        ).delete(synchronize_session=False)
        self.db_session.commit()
        return deleted_count

    def delete_all_expenses(self, profile_id: int) -> int:
        """Deletes all expenses for a given profile."""
        deleted_count = self.db_session.query(Expense).filter(
            Expense.profile_id == profile_id
        ).delete(synchronize_session=False)
        self.db_session.commit()
        return deleted_count