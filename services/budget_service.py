from sqlalchemy.orm import Session
from sqlalchemy import func
from models import Budget, Expense, Income, Category
from datetime import datetime, timedelta, timezone # Keep datetime, timedelta for general use
from utils.datetime_utils import wat_day_bounds_utc, wat_week_bounds_utc, wat_month_bounds_utc, to_wat, WAT # Import the new utilities

class BudgetService:
    def __init__(self, db_session: Session):
        self.db_session = db_session

    def set_budget(self, profile_id: int, amount: float, period: str, category_id: int = None):
        # Determine start and end dates based on period in UTC for DB storage
        # These functions return (start_utc, end_utc)
        if period == "daily":
            start_date_utc, end_date_utc = wat_day_bounds_utc()
        elif period == "weekly":
            start_date_utc, end_date_utc = wat_week_bounds_utc()
        elif period == "monthly":
            start_date_utc, end_date_utc = wat_month_bounds_utc()
        else:
            raise ValueError("Invalid period. Must be 'daily', 'weekly' or 'monthly'.")
        
        # Check if a budget for this period and category already exists for the profile
        existing_budget = self.db_session.query(Budget).filter(
            Budget.profile_id == profile_id,
            Budget.period == period,
            Budget.category_id == category_id,
            Budget.start_date <= end_date_utc, # Check for overlapping budgets
            Budget.end_date >= start_date_utc
        ).first()

        if existing_budget:
            existing_budget.amount = amount
            existing_budget.start_date = start_date_utc
            existing_budget.end_date = end_date_utc
            self.db_session.add(existing_budget)
            self.db_session.commit()
            self.db_session.refresh(existing_budget)
            return existing_budget
        else:
            new_budget = Budget(
                profile_id=profile_id,
                amount=amount,
                period=period,
                category_id=category_id,
                start_date=start_date_utc,
                end_date=end_date_utc
            )
            self.db_session.add(new_budget)
            self.db_session.commit()
            self.db_session.refresh(new_budget)
            return new_budget

    def get_budgets(self, profile_id: int, period: str = None):
        query = self.db_session.query(Budget).filter(Budget.profile_id == profile_id)
        if period:
            query = query.filter(Budget.period == period)
        return query.all()

    def get_expenses_for_budget_period(self, profile_id: int, start_date: datetime, end_date: datetime, category_id: int = None):
        query = self.db_session.query(func.sum(Expense.amount)).filter(
            Expense.profile_id == profile_id,
            Expense.date >= start_date,
            Expense.date < end_date # Use < end_date for proper interval
        )
        if category_id:
            query = query.filter(Expense.category_id == category_id)
        return query.scalar() or 0

    def get_income_for_budget_period(self, profile_id: int, start_date: datetime, end_date: datetime):
        query = self.db_session.query(func.sum(Income.amount)).filter(
            Income.profile_id == profile_id,
            Income.date >= start_date,
            Income.date < end_date # Use < end_date for proper interval
        )
        return query.scalar() or 0

    def get_budget_status(self, profile_id: int, start_date: datetime, end_date: datetime, period: str):
        budgets = self.db_session.query(Budget).filter(
            Budget.profile_id == profile_id,
            Budget.period == period,
            Budget.start_date <= end_date,
            Budget.end_date >= start_date
        ).all()

        detailed_budget_statuses = []

        for budget in budgets:
            category_name = budget.category.name if budget.category else "Overall"
            is_overall_budget = True if budget.category is None else False
            total_spent = self.get_expenses_for_budget_period(profile_id, start_date, end_date, budget.category_id)
            
            budget_amount = budget.amount
            remaining_amount = budget_amount - total_spent
            percentage_spent = (total_spent / budget_amount) * 100 if budget_amount > 0 else (100 if total_spent > 0 else 0)
            
            status = "no_budget"
            if budget_amount > 0:
                if total_spent > budget_amount:
                    status = "over"
                elif percentage_spent >= 90: # Close to budget
                    status = "close"
                elif total_spent == budget_amount:
                    status = "on_budget"
                else:
                    status = "under"
            elif total_spent > 0: # Budget is 0 but spent something
                status = "over"

            detailed_budget_statuses.append({
                "category_name": category_name,
                "budget_amount": budget_amount,
                "spent_amount": total_spent,
                "remaining_amount": remaining_amount,
                "percentage_spent": percentage_spent,
                "is_overall_budget": is_overall_budget,
                "status": status
            })

        return detailed_budget_statuses