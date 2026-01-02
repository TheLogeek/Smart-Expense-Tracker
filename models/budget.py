from sqlalchemy import Column, Integer, String, ForeignKey, Float, DateTime
from sqlalchemy.orm import relationship
from models.base import Base
import datetime

class Budget(Base):
    __tablename__ = "budgets"

    id = Column(Integer, primary_key=True, index=True)
    profile_id = Column(Integer, ForeignKey("profiles.id"), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True) # Null for overall budget
    amount = Column(Float, nullable=False)
    period = Column(String, nullable=False) # 'daily', 'weekly', 'monthly'
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)

    profile = relationship("Profile", back_populates="budgets")
    category = relationship("Category")

    def __repr__(self):
        return f"<Budget(profile_id={self.profile_id}, category_id={self.category_id}, amount={self.amount}, period='{self.period}')>"
