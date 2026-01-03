import streamlit as st
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy.orm import Session
from sqlalchemy import func # Import func for sum
from models import SessionLocal, User, Payment # Import Payment model
from services import SubscriptionService, MONTHLY_PRO_PRICE, YEARLY_PRO_PRICE # Import price constants
import datetime
from datetime import timezone # Import timezone
import pandas as pd
from utils.datetime_utils import AFRICA_LAGOS_TZ # Import AFRICA_LAGOS_TZ


def check_password():
    """Returns `True` if the user enters the correct password."""

    if "password_correct" not in st.session_state:
        st.session_state["username"] = st.text_input("Username", key="username_input")
        st.session_state["password"] = st.text_input(
            "Password", type="password", key="password_input"
        )
        if st.button("Login"): # Added Login button
            if st.session_state["username"] in st.secrets["admin"]["username"] and \
               st.session_state["password"] == st.secrets["admin"]["password"]:
                st.session_state["password_correct"] = True
                del st.session_state["password_input"]  # don't store password in session state after verification
                del st.session_state["username_input"] # don't store username either
            else:
                st.session_state["password_correct"] = False
        st.info("Please enter the admin credentials.")
        return False
    elif not st.session_state["password_correct"]:
        # Password not correct, show input + error.
        st.session_state["username"] = st.text_input("Username", key="username_input_fail")
        st.session_state["password"] = st.text_input(
            "Password", type="password", key="password_input_fail"
        )
        if st.button("Login"): # Added Login button for retries
            if st.session_state["username"] in st.secrets["admin"]["username"] and \
               st.session_state["password"] == st.secrets["admin"]["password"]:
                st.session_state["password_correct"] = True
                del st.session_state["password_input_fail"]
                del st.session_state["username_input_fail"]
            else:
                st.session_state["password_correct"] = False
        st.error("😕 User not known or password incorrect")
        return False
    else:
        # Password correct.
        return True

# --- Dashboard Content ---
def display_dashboard():
    st.title("Smart Expense Tracker Admin Dashboard")

    st.write("Welcome, Admin!")

    db_session = SessionLocal()
    try:
        sub_service = SubscriptionService(db_session)

        # Key Metrics Summary
        st.header("Key Metrics Summary")

        total_users = db_session.query(User).count()
        paying_users = db_session.query(User).filter(User.subscription_plan == "pro_paid").count()
        
        # Corrected MRR/Total Revenue calculation using imported constants
        now_utc = datetime.datetime.now(timezone.utc)
        monthly_pro_users = db_session.query(User).filter(
            User.subscription_plan == "pro_paid",
            User.subscription_duration == "monthly",
            User.subscription_end_date > now_utc
        ).count()

        yearly_pro_users = db_session.query(User).filter(
            User.subscription_plan == "pro_paid",
            User.subscription_duration == "yearly",
            User.subscription_end_date > now_utc
        ).count()

        # Calculate estimated_mrr based on current active subscribers
        estimated_mrr = (monthly_pro_users * MONTHLY_PRO_PRICE) + (yearly_pro_users * YEARLY_PRO_PRICE / 12)

        # Calculate estimated_total_revenue from all successful payment records
        total_payments_sum = db_session.query(func.sum(Payment.amount)).filter(
            Payment.status == "successful"
        ).scalar() or 0
        estimated_total_revenue = total_payments_sum

        # Calculate new users in the last 24 hours
        twenty_four_hours_ago = datetime.datetime.now(timezone.utc) - datetime.timedelta(hours=24)
        new_users_last_24h = db_session.query(User).filter(User.created_at > twenty_four_hours_ago).count()

        st.metric(label="Total Users", value=total_users)
        st.metric(label="New Users (24h)", value=new_users_last_24h) # New Metric
        st.metric(label="Paying Users", value=paying_users)
        st.metric(label="Estimated MRR (₦)", value=f"{int(estimated_mrr):,}")
        st.metric(label="Estimated Total Revenue (₦)", value=f"{int(estimated_total_revenue):,}")
        
        st.subheader("User Overview")
        users_data = db_session.query(User).all()
        # Convert to DataFrame for easy display
        users_df = pd.DataFrame([
            {
                "Telegram ID": u.telegram_id,
                "Username": u.username,
                "First Name": u.first_name,
                "Is Pro": u.is_pro,
                "Subscription Plan": u.subscription_plan,
                "Created At": u.created_at.astimezone(AFRICA_LAGOS_TZ).strftime("%Y-%m-%d %H:%M:%S") if u.created_at else "N/A",
                "Trial End Date": u.trial_end_date.astimezone(AFRICA_LAGOS_TZ).strftime("%Y-%m-%d %H:%M:%S %Z%z") if u.trial_end_date else "N/A",
                "Subscription End Date": u.subscription_end_date.astimezone(AFRICA_LAGOS_TZ).strftime("%Y-%m-%d %H:%M:%S %Z%z") if u.subscription_end_date else "N/A"
            } for u in users_data
        ])
        st.dataframe(users_df)

    finally:
        db_session.close()

# --- Main App Logic ---
if check_password():
    display_dashboard()
