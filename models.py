from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, JSON, create_engine, ForeignKey, func
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
import datetime

Base = declarative_base()

class Event(Base):
    __tablename__ = "events"
    id = Column(Integer, primary_key=True)
    platform = Column(String, nullable=False)  # shopify, whop, stripe, discord
    event_type = Column(String, nullable=False)
    payload = Column(JSON, nullable=False)
    received_at = Column(DateTime, default=func.now())
    processed = Column(Boolean, default=False)
    processed_at = Column(DateTime, nullable=True)
    idempotency_key = Column(String, nullable=True, index=True)

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String, index=True)
    external_id = Column(String, index=True)  # e.g., shopify customer id or whop user id
    metadata = Column(JSON, default={})

class Entitlement(Base):
    __tablename__ = "entitlements"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    product_code = Column(String, index=True)
    platform = Column(String)  # which platform grants this entitlement
    active = Column(Boolean, default=True)
    granted_at = Column(DateTime, default=func.now())
    revoked_at = Column(DateTime, nullable=True)
    user = relationship("User")

class Task(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True)
    type = Column(String, nullable=False)
    payload = Column(JSON, nullable=False)
    attempts = Column(Integer, default=0)
    max_attempts = Column(Integer, default=5)
    last_error = Column(Text, nullable=True)
    state = Column(String, default="pending")  # pending, in_progress, failed, done
    created_at = Column(DateTime, default=func.now())
    run_after = Column(DateTime, default=func.now())

class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"
    id = Column(Integer, primary_key=True)
    key = Column(String, index=True, unique=True)
    created_at = Column(DateTime, default=func.now())

# Database helper
def get_engine(database_url="sqlite:///./integration.db"):
    return create_engine(database_url, connect_args={"check_same_thread": False})

def get_sessionmaker(engine):
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)

def init_db(database_url="sqlite:///./integration.db"):
    engine = get_engine(database_url)
    Base.metadata.create_all(engine)
    return get_sessionmaker(engine)
