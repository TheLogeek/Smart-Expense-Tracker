from sqlalchemy import Column, Integer, String, ForeignKey, BigInteger # Import BigInteger
from sqlalchemy.orm import relationship
from models.base import Base

class Profile(Base):
    __tablename__ = "profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(BigInteger, ForeignKey("users.telegram_id"), nullable=False)
    name = Column(String, nullable=False)
    profile_type = Column(String, nullable=False) # 'personal' or 'business'

    user = relationship("User", foreign_keys=[user_id], back_populates="profiles")
    expenses = relationship("Expense", back_populates="profile")
    incomes = relationship("Income", back_populates="profile")
    budgets = relationship("Budget", back_populates="profile")
    categories = relationship("Category", back_populates="profile")

    def __repr__(self):
        return f"<Profile(user_id={self.user_id}, name='{self.name}', type='{self.profile_type}')>"
