"""
models.py — SQLAlchemy ORM models.
These map directly to tables in SQL Server.
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, DateTime, Text,
    Boolean, Float, ForeignKey, Enum
)
from sqlalchemy.orm import relationship
import enum

from api.database import Base


class Priority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TicketStatus(str, enum.Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    ESCALATED = "escalated"
    RESOLVED = "resolved"
    CLOSED = "closed"


class TicketCategory(str, enum.Enum):
    HARDWARE = "hardware"
    SOFTWARE = "software"
    NETWORK = "network"
    ACCESS = "access"
    PERFORMANCE = "performance"
    SECURITY = "security"
    OTHER = "other"


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    priority = Column(String(20), default=Priority.MEDIUM, nullable=False)
    status = Column(String(20), default=TicketStatus.OPEN, nullable=False)
    category = Column(String(20), default=TicketCategory.OTHER, nullable=False)
    assignee = Column(String(100), nullable=True)
    reporter = Column(String(100), nullable=True)
    source = Column(String(50), default="manual")  # manual | auto | escalation
    escalated = Column(Boolean, default=False)
    escalation_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)
    sla_breached = Column(Boolean, default=False)

    events = relationship("TicketEvent", back_populates="ticket", cascade="all, delete")


class TicketEvent(Base):
    """Audit log of everything that happens to a ticket."""
    __tablename__ = "ticket_events"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id"), nullable=False)
    event_type = Column(String(50), nullable=False)  # created, escalated, resolved, etc.
    message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    ticket = relationship("Ticket", back_populates="events")


class HealthCheck(Base):
    """Log of every health check run by the monitor."""
    __tablename__ = "health_checks"

    id = Column(Integer, primary_key=True, index=True)
    target = Column(String(255), nullable=False)   # URL, hostname, or "local"
    check_type = Column(String(50), nullable=False) # http, port, disk, cpu, ram
    status = Column(String(20), nullable=False)     # ok | warning | critical
    value = Column(Float, nullable=True)            # e.g. 87.3 for disk %
    message = Column(String(500), nullable=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id"), nullable=True)
    checked_at = Column(DateTime, default=datetime.utcnow)
