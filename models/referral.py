from sqlalchemy import Column, Integer, Boolean, DateTime, ForeignKey, BigInteger # Import BigInteger
from sqlalchemy.orm import relationship
from models.base import Base
import datetime
from datetime import timezone # Import timezone

class Referral(Base):
    __tablename__ = "referrals"

    id = Column(Integer, primary_key=True, index=True)
    referrer_id = Column(BigInteger, ForeignKey("users.telegram_id"), nullable=False)
    referred_id = Column(BigInteger, ForeignKey("users.telegram_id"), nullable=False, unique=True)
    profile_creation_reward_granted = Column(Boolean, default=False) # New field for first bonus
    upgrade_bonuses_granted_count = Column(Integer, default=0) # Tracks number of upgrade bonuses granted
    referral_date = Column(DateTime(timezone=True), default=lambda: datetime.datetime.now(timezone.utc)) # Make timezone-aware UTC

    referrer = relationship("User", foreign_keys=[referrer_id], back_populates="referred_users")
    referred = relationship("User", foreign_keys=[referred_id], back_populates="referred_by_info") # Updated back_populates

    def __repr__(self):
        return f"<Referral(referrer_id={self.referrer_id}, referred_id={self.referred_id}, profile_creation_reward_granted={self.profile_creation_reward_granted}, upgrade_bonuses_granted_count={self.upgrade_bonuses_granted_count})>"
