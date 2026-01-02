from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, BigInteger # Import BigInteger
from sqlalchemy.orm import relationship
from models.base import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(BigInteger, unique=True, index=True, nullable=False)
    username = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    is_pro = Column(Boolean, default=False)
    trial_start_date = Column(DateTime(timezone=True), nullable=True)
    trial_end_date = Column(DateTime(timezone=True), nullable=True)
    referred_by = Column(BigInteger, nullable=True) # telegram_id of referrer
    
    # Subscription details
    subscription_start_date = Column(DateTime(timezone=True), nullable=True)
    subscription_end_date = Column(DateTime(timezone=True), nullable=True)
    subscription_plan = Column(String, nullable=True) # 'free', 'pro_trial', 'pro_paid'
    subscription_duration = Column(String, nullable=True) # 'monthly', 'yearly' - for pro_paid plans

    daily_reminders_enabled = Column(Boolean, default=True)
    current_profile_id = Column(Integer, ForeignKey("profiles.id"), nullable=True)

    referred_users = relationship("Referral", foreign_keys="Referral.referrer_id", back_populates="referrer")
    referred_by_info = relationship("Referral", foreign_keys="Referral.referred_id", back_populates="referred", uselist=False)
    profiles = relationship("Profile", foreign_keys="Profile.user_id", back_populates="user")
    current_profile = relationship("Profile", foreign_keys=[current_profile_id])
    payments = relationship("Payment", back_populates="user") # New: Link to Payment model


    def __repr__(self):
        return f"<User(telegram_id={self.telegram_id}, username='{self.username}', is_pro={self.is_pro})>"