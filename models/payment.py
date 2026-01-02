from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, BigInteger # Import BigInteger
from sqlalchemy.orm import relationship
from models.base import Base
import datetime
from datetime import timezone

class Payment(Base):
    __tablename__ = "payments_log" # Renamed to avoid conflict with payments folder

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(BigInteger, ForeignKey("users.telegram_id"), nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String, default="NGN")
    plan_type = Column(String, nullable=False) # 'monthly' or 'yearly'
    payment_date = Column(DateTime(timezone=True), default=lambda: datetime.datetime.now(timezone.utc))
    reference = Column(String, unique=True, nullable=False) # Paystack transaction reference
    status = Column(String, default="successful") # 'successful', 'failed', 'pending'

    user = relationship("User", back_populates="payments")

    def __repr__(self):
        return f"<Payment(user_id={self.user_id}, amount={self.amount}, plan_type='{self.plan_type}', status='{self.status}')>"