from sqlalchemy import Column, Integer, String, ForeignKey, Float, DateTime
from sqlalchemy.orm import relationship
from models.base import Base, SessionLocal
import datetime
import zoneinfo
from zoneinfo import ZoneInfo # Explicitly import ZoneInfo

AFRICA_LAGOS_TZ = ZoneInfo("Africa/Lagos")

class Expense(Base):

    __tablename__ = "expenses"



    id = Column(Integer, primary_key=True, index=True)

    profile_id = Column(Integer, ForeignKey("profiles.id"), nullable=False)

    amount = Column(Float, nullable=False)

    description = Column(String, nullable=True)

    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)

    date = Column(DateTime(timezone=True), default=datetime.datetime.utcnow)



    profile = relationship("Profile", back_populates="expenses")

    category = relationship("Category", back_populates="expenses")



    def __repr__(self):

        return f"<Expense(profile_id={self.profile_id}, amount={self.amount}, description='{self.description}', date={self.date})>"



class Category(Base):

    __tablename__ = "categories"



    id = Column(Integer, primary_key=True, index=True)

    name = Column(String, nullable=False) # Not unique globally, unique per profile or default

    profile_id = Column(Integer, ForeignKey("profiles.id"), nullable=True) # Null for default, not null for custom



    profile = relationship("Profile", back_populates="categories")

    expenses = relationship("Expense", back_populates="category")



    def __repr__(self):

        return f"<Category(name='{self.name}', profile_id={self.profile_id})>"



def add_default_categories(db_session: SessionLocal):

    default_categories = [

        "Food", "Transport", "Utilities", "Entertainment", "Shopping",

        "Health", "Education", "Rent", "Gifts", "Other"

    ]

    for cat_name in default_categories:

        # Check if category exists either as a default or a user-specific one

        if not db_session.query(Category).filter_by(name=cat_name, profile_id=None).first():

            category = Category(name=cat_name, profile_id=None) # profile_id=None for default categories

            db_session.add(category)

    db_session.commit()
