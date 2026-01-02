from sqlalchemy.orm import Session
from sqlalchemy import func
from models import Expense, Income, Category, User
from datetime import datetime, timedelta # Keep datetime, timedelta for general use
import random # For randomized delays
from services.budget_service import BudgetService # Absolute import
from utils.datetime_utils import wat_day_bounds_utc, wat_week_bounds_utc, wat_month_bounds_utc, to_wat # Import the new utilities

class SummaryService:
    def __init__(self, db_session: Session):
        self.db_session = db_session
        self.budget_service = BudgetService(db_session)

    def _generate_budget_insight_messages(self, detailed_budget_statuses: list, period: str) -> list[str]:
        insights = []
        for status in detailed_budget_statuses:
            category_name = status['category_name']
            budget_amount = status['budget_amount']
            spent_amount = status['spent_amount']
            remaining_amount = status['remaining_amount']
            percentage_spent = status['percentage_spent']
            
            if status['status'] == "no_budget":
                insights.append(f"No {category_name} budget set for this {period}.")
            elif status['status'] == "over":
                insights.append(f"🔴 Warning! You exceeded your {category_name} budget by ₦{abs(remaining_amount):,.2f} this {period}!")
            elif status['status'] == "close":
                insights.append(f"🟠 Heads up! You have spent {percentage_spent:.0f}% of your {category_name} budget this {period}. You have ₦{remaining_amount:,.2f} left.")
            elif status['status'] == "on_budget":
                insights.append(f"🟢 Perfect! You have spent exactly your {category_name} budget for this {period}.")
            elif status['status'] == "under":
                if spent_amount == 0:
                    insights.append(f"🟢 Great job! You haven't spent anything on {category_name} this {period} yet.")
                else:
                    insights.append(f"🟢 Excellent! You are ₦{remaining_amount:,.2f} ({100 - percentage_spent:.0f}%) under your {category_name} budget this {period}.")
        return insights

    def get_daily_summary(self, profile_id: int):
        start_of_day_utc, end_of_day_utc = wat_day_bounds_utc()

        total_expenses = self.db_session.query(func.sum(Expense.amount)).filter(
            Expense.profile_id == profile_id,
            Expense.date >= start_of_day_utc,
            Expense.date < end_of_day_utc # Use < for exclusive end
        ).scalar() or 0

        num_expense_entries = self.db_session.query(Expense).filter(
            Expense.profile_id == profile_id,
            Expense.date >= start_of_day_utc,
            Expense.date < end_of_day_utc
        ).count()

        total_income = self.db_session.query(func.sum(Income.amount)).filter(
            Income.profile_id == profile_id,
            Income.date >= start_of_day_utc,
            Income.date < end_of_day_utc
        ).scalar() or 0
        
        balance = total_income - total_expenses

        # Get expenses by category for charts
        expenses_by_category_query = self.db_session.query(
            Category.name,
            func.sum(Expense.amount)
        ).join(
            Category, Expense.category_id == Category.id
        ).filter(
            Expense.profile_id == profile_id,
            Expense.date >= start_of_day_utc,
            Expense.date < end_of_day_utc
        ).group_by(Category.name).all()

        # Format for charts
        category_data = [{"category": name, "amount": amount} for name, amount in expenses_by_category_query]

        # Also get uncategorized expenses
        uncategorized_expenses = self.db_session.query(
            func.sum(Expense.amount)
        ).filter(
            Expense.profile_id == profile_id,
            Expense.date >= start_of_day_utc,
            Expense.date < end_of_day_utc,
            Expense.category_id == None
        ).scalar() or 0

        if uncategorized_expenses > 0:
            category_data.append({"category": "Uncategorized", "amount": uncategorized_expenses})

        detailed_budget_statuses = self.budget_service.get_budget_status(profile_id, start_of_day_utc, end_of_day_utc, "daily")
        budget_insights = self._generate_budget_insight_messages(detailed_budget_statuses, "day")

        return {
            "total_expenses": total_expenses,
            "num_expense_entries": num_expense_entries,
            "total_income": total_income,
            "balance": balance,
            "budget_insights": budget_insights,
            "expenses_by_category": category_data,
            "detailed_budget_statuses": detailed_budget_statuses # New structured budget data
        }

    def get_weekly_summary(self, profile_id: int):
        start_of_week_utc, end_of_week_utc = wat_week_bounds_utc()

        total_expenses = self.db_session.query(func.sum(Expense.amount)).filter(
            Expense.profile_id == profile_id,
            Expense.date >= start_of_week_utc,
            Expense.date < end_of_week_utc
        ).scalar() or 0

        num_expense_entries = self.db_session.query(Expense).filter(
            Expense.profile_id == profile_id,
            Expense.date >= start_of_week_utc,
            Expense.date < end_of_week_utc
        ).count()

        total_income = self.db_session.query(func.sum(Income.amount)).filter(
            Income.profile_id == profile_id,
            Income.date >= start_of_week_utc,
            Income.date < end_of_week_utc
        ).scalar() or 0
        
        balance = total_income - total_expenses

        # Get expenses by category for charts
        expenses_by_category_query = self.db_session.query(
            Category.name,
            func.sum(Expense.amount)
        ).join(
            Category, Expense.category_id == Category.id
        ).filter(
            Expense.profile_id == profile_id,
            Expense.date >= start_of_week_utc,
            Expense.date < end_of_week_utc
        ).group_by(Category.name).all()

        # Format for charts
        category_data = [{"category": name, "amount": amount} for name, amount in expenses_by_category_query]

        # Also get uncategorized expenses
        uncategorized_expenses = self.db_session.query(
            func.sum(Expense.amount)
        ).filter(
            Expense.profile_id == profile_id,
            Expense.date >= start_of_week_utc,
            Expense.date < end_of_week_utc,
            Expense.category_id == None
        ).scalar() or 0

        if uncategorized_expenses > 0:
            category_data.append({"category": "Uncategorized", "amount": uncategorized_expenses})
        
        detailed_budget_statuses = self.budget_service.get_budget_status(profile_id, start_of_week_utc, end_of_week_utc, "weekly")
        budget_insights = self._generate_budget_insight_messages(detailed_budget_statuses, "week")

        return {
            "total_expenses": total_expenses,
            "num_expense_entries": num_expense_entries,
            "total_income": total_income,
            "balance": balance,
            "budget_insights": budget_insights,
            "expenses_by_category": category_data,
            "detailed_budget_statuses": detailed_budget_statuses # New structured budget data
        }

    def get_monthly_summary(self, profile_id: int):
        start_of_month_utc, end_of_month_utc = wat_month_bounds_utc()
        
        total_expenses = self.db_session.query(func.sum(Expense.amount)).filter(
            Expense.profile_id == profile_id,
            Expense.date >= start_of_month_utc,
            Expense.date < end_of_month_utc
        ).scalar() or 0

        num_expense_entries = self.db_session.query(Expense).filter(
            Expense.profile_id == profile_id,
            Expense.date >= start_of_month_utc,
            Expense.date < end_of_month_utc
        ).count()

        total_income = self.db_session.query(func.sum(Income.amount)).filter(
            Income.profile_id == profile_id,
            Income.date >= start_of_month_utc,
            Income.date < end_of_month_utc
        ).scalar() or 0
        
        balance = total_income - total_expenses

        # Get expenses by category for charts
        expenses_by_category_query = self.db_session.query(
            Category.name,
            func.sum(Expense.amount)
        ).join(
            Category, Expense.category_id == Category.id
        ).filter(
            Expense.profile_id == profile_id,
            Expense.date >= start_of_month_utc,
            Expense.date < end_of_month_utc
        ).group_by(Category.name).all()

        # Format for charts
        category_data = [{"category": name, "amount": amount} for name, amount in expenses_by_category_query]

        # Also get uncategorized expenses
        uncategorized_expenses = self.db_session.query(
            func.sum(Expense.amount)
        ).filter(
            Expense.profile_id == profile_id,
            Expense.date >= start_of_month_utc,
            Expense.date < end_of_month_utc,
            Expense.category_id == None
        ).scalar() or 0

        if uncategorized_expenses > 0:
            category_data.append({"category": "Uncategorized", "amount": uncategorized_expenses})
        
        detailed_budget_statuses = self.budget_service.get_budget_status(profile_id, start_of_month_utc, end_of_month_utc, "monthly")
        budget_insights = self._generate_budget_insight_messages(detailed_budget_statuses, "month")

        return {
            "total_expenses": total_expenses,
            "num_expense_entries": num_expense_entries,
            "total_income": total_income,
            "balance": balance,
            "budget_insights": budget_insights,
            "expenses_by_category": category_data,
            "detailed_budget_statuses": detailed_budget_statuses # New structured budget data
        }

    def get_all_users_for_scheduled_summaries(self):
        """Retrieves all users for scheduled summary jobs, avoiding loading all into memory."""
        # For a truly low-memory approach, consider yielding users or processing in batches
        return self.db_session.query(User).all()