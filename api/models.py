"""
models.py — SQLAlchemy ORM models.

Priorities, statuses, categories and sources are now normalized into
their own lookup tables. Tickets reference them via foreign keys,
which enforces valid values at the database level.
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, DateTime, Text,
    Boolean, Float, ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import relationship

from api.database import Base


# ── Lookup tables ────────────────────────────────────────────────────────────

class TicketPriority(Base):
    __tablename__ = "ticket_priorities"

    id   = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False, unique=True)  # critical, high, medium, low

    tickets = relationship("Ticket", back_populates="priority_ref")

    def __repr__(self):
        return f"<Priority {self.name}>"


class TicketStatus(Base):
    __tablename__ = "ticket_statuses"

    id   = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False, unique=True)  # open, in_progress, escalated, resolved, closed

    tickets = relationship("Ticket", back_populates="status_ref")

    def __repr__(self):
        return f"<Status {self.name}>"


class TicketCategory(Base):
    __tablename__ = "ticket_categories"

    id   = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False, unique=True)  # hardware, software, network, ...

    tickets = relationship("Ticket", back_populates="category_ref")

    def __repr__(self):
        return f"<Category {self.name}>"


class TicketSource(Base):
    __tablename__ = "ticket_sources"

    id   = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False, unique=True)  # manual, auto, escalation

    tickets = relationship("Ticket", back_populates="source_ref")

    def __repr__(self):
        return f"<Source {self.name}>"


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
    created_at       = Column(DateTime, default=datetime.utcnow)
    updated_at       = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    resolved_at      = Column(DateTime, nullable=True)

    # Foreign keys to lookup tables
    priority_id  = Column(Integer, ForeignKey("ticket_priorities.id"), nullable=False)
    status_id    = Column(Integer, ForeignKey("ticket_statuses.id"),   nullable=False)
    category_id  = Column(Integer, ForeignKey("ticket_categories.id"), nullable=False)
    source_id    = Column(Integer, ForeignKey("ticket_sources.id"),    nullable=False)

    # Relationships
    priority_ref = relationship("TicketPriority", back_populates="tickets")
    status_ref   = relationship("TicketStatus",   back_populates="tickets")
    category_ref = relationship("TicketCategory", back_populates="tickets")
    source_ref   = relationship("TicketSource",   back_populates="tickets")
    events       = relationship("TicketEvent", back_populates="ticket", cascade="all, delete")

    # Convenience properties so the rest of the code can still do ticket.priority
    @property
    def priority(self):
        return self.priority_ref.name if self.priority_ref else None

    @property
    def status(self):
        return self.status_ref.name if self.status_ref else None

    @property
    def category(self):
        return self.category_ref.name if self.category_ref else None

    @property
    def source(self):
        return self.source_ref.name if self.source_ref else None


class TicketEvent(Base):
    """Audit log — every change to a ticket is recorded here."""
    __tablename__ = "ticket_events"

    id         = Column(Integer, primary_key=True, index=True)
    ticket_id  = Column(Integer, ForeignKey("tickets.id"), nullable=False)
    event_type = Column(String(50), nullable=False)
    message    = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    ticket = relationship("Ticket", back_populates="events")


class HealthCheck(Base):
    """Log of every health check run by the monitor."""
    __tablename__ = "health_checks"

    id         = Column(Integer, primary_key=True, index=True)
    target     = Column(String(255), nullable=False)
    check_type = Column(String(50),  nullable=False)
    status     = Column(String(20),  nullable=False)
    value      = Column(Float,       nullable=True)
    message    = Column(String(500), nullable=True)
    ticket_id  = Column(Integer, ForeignKey("tickets.id"), nullable=True)
    checked_at = Column(DateTime, default=datetime.utcnow)
