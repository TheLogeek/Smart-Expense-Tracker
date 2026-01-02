import logging
from sqlalchemy.orm import Session
from models import Income
from datetime import datetime, timezone # Updated import to include timezone
import re
from sqlalchemy import func, delete # Import delete

class IncomeService:
    def __init__(self, db_session: Session):
        self.db_session = db_session

    def add_income(self, profile_id: int, amount: float, source: str):
        income = Income(
            profile_id=profile_id,
            amount=amount,
            source=source,
            date=datetime.now(timezone.utc) # Store as UTC
        )
        self.db_session.add(income)
        self.db_session.commit()
        self.db_session.refresh(income)
        return income

    def parse_income_message(self, message_text: str):
        # Regex to match "[amount] from [source]" or "earned [amount] from [source]"
        pattern = re.compile(r"(?:(?:earned|received)\s+)?(\d+(?:[.,]\d{1,2})?)\s+(?:from|for)\s+(.+)", re.IGNORECASE)
        match = pattern.match(message_text.strip())
        if match:
            amount_str = match.group(1).replace(',', '.') # Handle comma as decimal separator
            amount = float(amount_str)
            source = match.group(2).strip()
            return amount, source
        return None, None

    def get_incomes_by_profile(self, profile_id: int):
        incomes = self.db_session.query(Income).filter(Income.profile_id == profile_id).order_by(Income.date).all()
        for inc in incomes:
            if inc.date and inc.date.tzinfo is None:
                inc.date = inc.date.replace(tzinfo=timezone.utc) # Assume naive is UTC
            logging.info(f"Income ID: {inc.id}, Date: {inc.date}, TZInfo: {inc.date.tzinfo}, Type: {type(inc.date)}")
        return incomes

    def delete_incomes_by_date_range(self, profile_id: int, start_date_utc: datetime, end_date_utc: datetime) -> int:
        """Deletes incomes for a given profile within a specified UTC date range."""
        deleted_count = self.db_session.query(Income).filter(
            Income.profile_id == profile_id,
            Income.date >= start_date_utc,
            Income.date < end_date_utc
        ).delete(synchronize_session=False)
        self.db_session.commit()
        return deleted_count

    def delete_all_incomes(self, profile_id: int) -> int:
        """Deletes all incomes for a given profile."""
        deleted_count = self.db_session.query(Income).filter(
            Income.profile_id == profile_id
        ).delete(synchronize_session=False)
        self.db_session.commit()
        return deleted_count


