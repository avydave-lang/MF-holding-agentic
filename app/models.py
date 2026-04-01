from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, Float, Boolean,
    DateTime, ForeignKey, JSON
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class SiteRecord(Base):
    __tablename__ = "site_records"

    id = Column(Integer, primary_key=True)
    domain_hash = Column(String(64), unique=True, nullable=False, index=True)
    url = Column(Text, nullable=False)
    dom_hash = Column(String(64), nullable=True)
    last_success_at = Column(DateTime, nullable=True)
    script_version = Column(Integer, default=0, nullable=False)
    script_content = Column(Text, nullable=True)
    site_fingerprint_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    events = relationship("ScrapeEvent", back_populates="site", cascade="all, delete-orphan")
    healing_history = relationship("HealingHistory", back_populates="site", cascade="all, delete-orphan")


class ScrapeEvent(Base):
    __tablename__ = "scrape_events"

    id = Column(Integer, primary_key=True)
    site_id = Column(Integer, ForeignKey("site_records.id"), nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    status = Column(String(32), nullable=False)  # SUCCESS | FAILED | LOW_CONFIDENCE | ESCALATED
    confidence_score = Column(Float, nullable=True)
    error_type = Column(String(128), nullable=True)
    error_trace = Column(Text, nullable=True)
    healing_tier_used = Column(Integer, nullable=True)  # 1, 2, 3 or null

    site = relationship("SiteRecord", back_populates="events")
    healing_history = relationship("HealingHistory", back_populates="event", cascade="all, delete-orphan")
    result = relationship("ScrapeResult", back_populates="event", uselist=False, cascade="all, delete-orphan")


class HealingHistory(Base):
    __tablename__ = "healing_history"

    id = Column(Integer, primary_key=True)
    site_id = Column(Integer, ForeignKey("site_records.id"), nullable=False)
    event_id = Column(Integer, ForeignKey("scrape_events.id"), nullable=False)
    tier = Column(Integer, nullable=False)
    old_selector = Column(Text, nullable=True)
    new_selector = Column(Text, nullable=True)
    prompt_used = Column(Text, nullable=True)
    success = Column(Boolean, default=False, nullable=False)
    applied_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    site = relationship("SiteRecord", back_populates="healing_history")
    event = relationship("ScrapeEvent", back_populates="healing_history")


class ScrapeResult(Base):
    __tablename__ = "scrape_results"

    id = Column(Integer, primary_key=True)
    event_id = Column(Integer, ForeignKey("scrape_events.id"), unique=True, nullable=False)
    data = Column(JSON, nullable=False)
    confidence_score = Column(Float, nullable=False)
    confidence_flags = Column(JSON, nullable=True)  # list of flag strings
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    event = relationship("ScrapeEvent", back_populates="result")
