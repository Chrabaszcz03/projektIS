import os
from sqlalchemy import Column, Integer, String, Float, Date, Text, ForeignKey, create_engine
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "crypto_events.db")


class Cryptocurrency(Base):
    __tablename__ = 'cryptocurrencies'
    id = Column(Integer, primary_key=True)
    symbol = Column(String, unique=True)
    name = Column(String)
    prices = relationship("PriceHistory", back_populates="crypto")


class PriceHistory(Base):
    __tablename__ = 'price_history'
    id = Column(Integer, primary_key=True)
    crypto_id = Column(Integer, ForeignKey('cryptocurrencies.id'))
    date = Column(Date)
    price = Column(Float)
    crypto = relationship("Cryptocurrency", back_populates="prices")


class EventCategory(Base):
    __tablename__ = 'event_categories'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    events = relationship("Event", back_populates="category")


class Event(Base):
    __tablename__ = 'events'
    id = Column(Integer, primary_key=True)
    title = Column(String)
    description = Column(Text)
    date = Column(Date)
    category_id = Column(Integer, ForeignKey('event_categories.id'))
    category = relationship("EventCategory", back_populates="events")


class AnalysisResult(Base):
    __tablename__ = 'analysis_results'
    id                  = Column(Integer, primary_key=True)
    coin                = Column(String,  nullable=False)
    category            = Column(String,  nullable=False)
    n_event_days        = Column(Integer)
    n_control_days      = Column(Integer)
    mean_return_event   = Column(Float)
    mean_return_control = Column(Float)
    std_event           = Column(Float)
    std_control         = Column(Float)
    t_stat              = Column(Float)
    p_value             = Column(Float)
    significant         = Column(Integer)   # 1 = True, 0 = False


class User(Base):
    __tablename__ = "users"
    id              = Column(Integer, primary_key=True)
    username        = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)


def get_engine(conn_str: str | None = None):
    if conn_str:
        return create_engine(conn_str)
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return create_engine(f"sqlite:///{DB_PATH}")


def init_db(conn_str: str | None = None):
    Base.metadata.create_all(get_engine(conn_str))
