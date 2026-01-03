import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Load environment variables (for local development or environments like Render)
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

# If DATABASE_URL is not found via os.getenv, try st.secrets (for Streamlit Cloud)
if not DATABASE_URL:
    try:
        import streamlit as st
        if "DATABASE_URL" in st.secrets:
            DATABASE_URL = st.secrets["DATABASE_URL"]
    except:
        # Streamlit not installed or not running in a Streamlit context
        pass

if not DATABASE_URL:
    raise ValueError("DATABASE_URL is not set in environment variables or st.secrets.")

Base = declarative_base()

# Create the engine
engine = create_engine(DATABASE_URL, pool_pre_ping=True) # pool_pre_ping helps with connection dropouts

# Create a SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def create_all_tables():
    Base.metadata.create_all(engine)
