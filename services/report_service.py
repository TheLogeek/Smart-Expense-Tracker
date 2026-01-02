import io
import csv
from sqlalchemy.orm import Session
from services import ExpenseService, IncomeService
import datetime
from utils.datetime_utils import to_wat # Import to_wat

class ReportService:
    def __init__(self, db_session: Session):
        self.db_session = db_session
        self.expense_service = ExpenseService(db_session)
        self.income_service = IncomeService(db_session)

    def generate_csv_report(self, profile_id: int) -> io.BytesIO:
        """
        Generates a CSV report of all expenses and income for a given profile.
        Returns a BytesIO object containing the CSV data.
        """
        output = io.StringIO()
        writer = csv.writer(output)

        # Write header row
        writer.writerow(["Type", "Date", "Amount", "Description/Source", "Category"])

        # Fetch expenses
        expenses = self.expense_service.get_expenses_by_profile(profile_id)
        for exp in expenses:
            wat_date = to_wat(exp.date) # Convert to WAT for display
            writer.writerow(["Expense", wat_date.strftime("%Y-%m-%d %H:%M:%S %Z%z"), exp.amount, exp.description, exp.category.name if exp.category else "N/A"])

        # Fetch income
        incomes = self.income_service.get_incomes_by_profile(profile_id)
        for inc in incomes:
            wat_date = to_wat(inc.date) # Convert to WAT for display
            writer.writerow(["Income", wat_date.strftime("%Y-%m-%d %H:%M:%S %Z%z"), inc.amount, inc.source, "N/A"]) # Income doesn't have categories

        return io.BytesIO(output.getvalue().encode('utf-8'))

