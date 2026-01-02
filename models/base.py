import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Dynamically get DATABASE_URL from environment variable
DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL.startswith("sqlite:///"):
    # For SQLite, ensure relative path is handled correctly if needed, or keep absolute
    # For simplicity, if it's SQLite, we assume it's still local and might not need dynamic path if .env points to specific file
    pass 
else:
    # For PostgreSQL or other, connection args might differ.
    # We remove check_same_thread for PostgreSQL as it's not applicable.
    pass

Base = declarative_base()

# Create the engine
engine = create_engine(DATABASE_URL, pool_pre_ping=True) # pool_pre_ping helps with connection dropouts

# Create a SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def create_all_tables():
    Base.metadata.create_all(engine)
