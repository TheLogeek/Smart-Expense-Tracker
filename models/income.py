from sqlalchemy import Column, Integer, String, ForeignKey, Float, DateTime
from sqlalchemy.orm import relationship
from models.base import Base
import datetime
import zoneinfo
from zoneinfo import ZoneInfo # Explicitly import ZoneInfo

AFRICA_LAGOS_TZ = ZoneInfo("Africa/Lagos")

class Income(Base):
    __tablename__ = "incomes"

    id = Column(Integer, primary_key=True, index=True)
    profile_id = Column(Integer, ForeignKey("profiles.id"), nullable=False)
    amount = Column(Float, nullable=False)
    source = Column(String, nullable=True)
    date = Column(DateTime(timezone=True), default=datetime.datetime.utcnow)

    profile = relationship("Profile", back_populates="incomes")

    def __repr__(self):
        return f"<Income(profile_id={self.profile_id}, amount={self.amount}, source='{self.source}', date={self.date})>"
