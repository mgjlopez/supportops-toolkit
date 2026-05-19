"""
escalation_engine.py — SLA breach detector and escalation handler.
"""

import os
import sys
from datetime import datetime, timedelta, UTC

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from api.database import SessionLocal
from api.logger import get_logger
from api.models import Ticket, TicketEvent, TicketStatus
from automation.slack_notifier import notify_sla_breach, notify_escalation

log = get_logger(__name__)

SLA_RESPONSE_HOURS = {
    "critical": 0.25,
    "high":     1.0,
    "medium":   4.0,
    "low":      24.0,
}
MAX_ESCALATIONS = 3


def check_and_escalate():
    db = SessionLocal()
    now = datetime.now(UTC)
    escalated_count = 0
    breached_count = 0

    try:
        active_tickets = (
            db.query(Ticket)
            .join(Ticket.status_ref)
            .filter(TicketStatus.name.in_(["open", "in_progress"]))
            .all()
        )

        log.info("Starting escalation run", extra={"active_tickets": len(active_tickets)})

        for ticket in active_tickets:
            priority_name = ticket.priority_ref.name if ticket.priority_ref else "medium"
            sla_hours     = SLA_RESPONSE_HOURS.get(priority_name, 4.0)

            # Make created_at timezone-aware for comparison
            created_at = ticket.created_at.replace(tzinfo=UTC) if ticket.created_at.tzinfo is None else ticket.created_at
            sla_deadline = created_at + timedelta(hours=sla_hours)
            age_hours    = (now - created_at).total_seconds() / 3600

            if now > sla_deadline:
                if not ticket.sla_breached:
                    ticket.sla_breached = True
                    breached_count += 1
                    log.warning("SLA breached", extra={
                        "ticket_id": ticket.id,
                        "priority":  priority_name,
                        "age_hours": round(age_hours, 2),
                        "sla_hours": sla_hours,
                    })
                    notify_sla_breach(
                        ticket_id  = ticket.id,
                        title      = ticket.title,
                        priority   = priority_name,
                        age_hours  = age_hours,
                        sla_hours  = sla_hours,
                        assignee   = ticket.assignee,
                    )

                if not ticket.escalated and ticket.escalation_count < MAX_ESCALATIONS:
                    # Get escalated status ID
                    escalated_status = db.query(TicketStatus).filter(TicketStatus.name == "escalated").first()
                    if escalated_status:
                        ticket.status_id = escalated_status.id

                    ticket.escalated        = True
                    ticket.escalation_count += 1
                    ticket.updated_at       = now

                    db.add(TicketEvent(
                        ticket_id  = ticket.id,
                        event_type = "escalated",
                        message    = (
                            f"Auto-escalated by SLA engine. "
                            f"Priority: {priority_name}, "
                            f"Age: {age_hours:.1f}h, SLA: {sla_hours}h. "
                            f"Escalation #{ticket.escalation_count}."
                        ),
                        created_at = now,
                    ))

                    notify_escalation(
                        ticket_id        = ticket.id,
                        title            = ticket.title,
                        priority         = priority_name,
                        escalation_count = ticket.escalation_count,
                        age_hours        = age_hours,
                        assignee         = ticket.assignee,
                    )
                    escalated_count += 1
                    log.info("Ticket escalated", extra={
                        "ticket_id":        ticket.id,
                        "escalation_count": ticket.escalation_count,
                        "priority":         priority_name,
                    })

        db.commit()
        log.info("Escalation run complete", extra={
            "newly_breached": breached_count,
            "escalated":      escalated_count,
        })

    except Exception as e:
        db.rollback()
        log.error("Escalation engine error", extra={"error": str(e)})
    finally:
        db.close()

    return {"escalated": escalated_count, "breached": breached_count}


if __name__ == "__main__":
    result = check_and_escalate()
    log.info("Done", extra=result)
