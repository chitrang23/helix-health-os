from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models.orm import Base

SQLALCHEMY_DATABASE_URL = "sqlite:///./helix.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Re-create all tables matching ORM models
Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
