"""
models.py — SQLAlchemy ORM models.

Priorities, statuses, categories and sources are normalized into
lookup tables. Tickets reference them via foreign keys.

The convenience properties use a p_ prefix to avoid conflicting
with SQLAlchemy's internal attribute handling.
"""

from datetime import datetime, UTC
from sqlalchemy import (
    Column, Integer, String, DateTime, Text,
    Boolean, Float, ForeignKey,
)
from sqlalchemy.orm import relationship

from api.database import Base


# ── Lookup tables ─────────────────────────────────────────────────────────────

class TicketPriority(Base):
    __tablename__ = "ticket_priorities"
    id   = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False, unique=True)
    tickets = relationship("Ticket", back_populates="priority_ref")

class TicketStatus(Base):
    __tablename__ = "ticket_statuses"
    id   = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False, unique=True)
    tickets = relationship("Ticket", back_populates="status_ref")

class TicketCategory(Base):
    __tablename__ = "ticket_categories"
    id   = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False, unique=True)
    tickets = relationship("Ticket", back_populates="category_ref")

class TicketSource(Base):
    __tablename__ = "ticket_sources"
    id   = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False, unique=True)
    tickets = relationship("Ticket", back_populates="source_ref")


# ── Main tables ───────────────────────────────────────────────────────────────

class Ticket(Base):
    __tablename__ = "tickets"

    id               = Column(Integer, primary_key=True, index=True)
    title            = Column(String(255), nullable=False)
    description      = Column(Text, nullable=True)
    assignee         = Column(String(100), nullable=True)
    reporter         = Column(String(100), nullable=True)
    escalated        = Column(Boolean, default=False)
    escalation_count = Column(Integer, default=0)
    sla_breached     = Column(Boolean, default=False)
    created_at       = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at       = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))
    resolved_at      = Column(DateTime, nullable=True)

    # Foreign keys
    priority_id = Column(Integer, ForeignKey("ticket_priorities.id"), nullable=False)
    status_id   = Column(Integer, ForeignKey("ticket_statuses.id"),   nullable=False)
    category_id = Column(Integer, ForeignKey("ticket_categories.id"), nullable=False)
    source_id   = Column(Integer, ForeignKey("ticket_sources.id"),    nullable=False)

    # Relationships
    priority_ref = relationship("TicketPriority", back_populates="tickets")
    status_ref   = relationship("TicketStatus",   back_populates="tickets")
    category_ref = relationship("TicketCategory", back_populates="tickets")
    source_ref   = relationship("TicketSource",   back_populates="tickets")
    events       = relationship("TicketEvent", back_populates="ticket", cascade="all, delete")


class TicketEvent(Base):
    __tablename__ = "ticket_events"
    id         = Column(Integer, primary_key=True, index=True)
    ticket_id  = Column(Integer, ForeignKey("tickets.id"), nullable=False)
    event_type = Column(String(50), nullable=False)
    message    = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    ticket     = relationship("Ticket", back_populates="events")


class HealthCheck(Base):
    __tablename__ = "health_checks"
    id         = Column(Integer, primary_key=True, index=True)
    target     = Column(String(255), nullable=False)
    check_type = Column(String(50),  nullable=False)
    status     = Column(String(20),  nullable=False)
    value      = Column(Float,       nullable=True)
    message    = Column(String(500), nullable=True)
    ticket_id  = Column(Integer, ForeignKey("tickets.id"), nullable=True)
    checked_at = Column(DateTime, default=lambda: datetime.now(UTC))
