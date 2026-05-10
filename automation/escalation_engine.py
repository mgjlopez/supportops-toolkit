"""
escalation_engine.py — SLA breach detector and escalation handler.

Runs on a schedule and scans open tickets for SLA violations.
When a ticket exceeds its allowed response time, it is:
  1. Marked as escalated in the database
  2. Logged with an audit event
  3. Would send a notification (stubbed — easy to extend with email/Slack)

SLA thresholds (response time before first escalation):
  critical → 15 minutes
  high     → 1 hour
  medium   → 4 hours
  low      → 24 hours
"""

import os
import sys
import logging
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from api.database import SessionLocal
from api.models import Ticket, TicketEvent, TicketStatus

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [EscalationEngine] %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# SLA response windows (hours before first escalation)
SLA_RESPONSE_HOURS = {
    "critical": 0.25,   # 15 minutes
    "high": 1.0,
    "medium": 4.0,
    "low": 24.0,
}

# Max escalation count — stops re-escalating indefinitely
MAX_ESCALATIONS = 3


def check_and_escalate():
    """
    Main escalation logic.
    Queries all open/in-progress tickets and escalates those that have breached SLA.
    """
    db = SessionLocal()
    now = datetime.utcnow()
    escalated_count = 0
    breached_count = 0

    try:
        active_tickets = (
            db.query(Ticket)
            .filter(Ticket.status.in_([TicketStatus.OPEN, TicketStatus.IN_PROGRESS]))
            .all()
        )

        log.info(f"Checking {len(active_tickets)} active tickets for SLA compliance...")

        for ticket in active_tickets:
            sla_hours = SLA_RESPONSE_HOURS.get(ticket.priority, 4.0)
            sla_deadline = ticket.created_at + timedelta(hours=sla_hours)
            age_hours = (now - ticket.created_at).total_seconds() / 3600

            if now > sla_deadline:
                # Mark SLA as breached regardless of escalation status
                if not ticket.sla_breached:
                    ticket.sla_breached = True
                    breached_count += 1
                    log.warning(
                        f"🔴 SLA breached — Ticket #{ticket.id} [{ticket.priority}] "
                        f"'{ticket.title[:50]}' (age: {age_hours:.1f}h, SLA: {sla_hours}h)"
                    )

                # Escalate if not already at max
                if not ticket.escalated and ticket.escalation_count < MAX_ESCALATIONS:
                    ticket.escalated = True
                    ticket.escalation_count += 1
                    ticket.status = TicketStatus.ESCALATED
                    ticket.updated_at = now

                    db.add(TicketEvent(
                        ticket_id=ticket.id,
                        event_type="escalated",
                        message=(
                            f"Auto-escalated by SLA engine. "
                            f"Priority: {ticket.priority}, "
                            f"Age: {age_hours:.1f}h, "
                            f"SLA: {sla_hours}h. "
                            f"Escalation #{ticket.escalation_count}."
                        ),
                        created_at=now,
                    ))

                    _send_notification(ticket)
                    escalated_count += 1

                elif ticket.escalation_count >= MAX_ESCALATIONS:
                    log.info(
                        f"⏭️  Ticket #{ticket.id} already at max escalations ({MAX_ESCALATIONS})"
                    )
            else:
                remaining = (sla_deadline - now).total_seconds() / 60
                log.debug(
                    f"✅ Ticket #{ticket.id} within SLA — {remaining:.0f} min remaining"
                )

        db.commit()
        log.info(
            f"Escalation run complete. "
            f"Newly breached: {breached_count}, Escalated: {escalated_count}"
        )

    except Exception as e:
        db.rollback()
        log.error(f"Escalation engine error: {e}", exc_info=True)
    finally:
        db.close()

    return {"escalated": escalated_count, "breached": breached_count}


def _send_notification(ticket: Ticket):
    """
    Stub for escalation notifications.
    In a real deployment, replace this with:
      - Email via smtplib or SendGrid
      - Slack webhook (httpx.post to webhook URL)
      - PagerDuty API call
      - Teams webhook
    """
    log.info(
        f"📣 [NOTIFY] Ticket #{ticket.id} escalated — "
        f"'{ticket.title[:60]}' | Priority: {ticket.priority} | "
        f"Assignee: {ticket.assignee or 'unassigned'}"
    )
    # Example Slack webhook stub:
    # webhook_url = os.getenv("SLACK_WEBHOOK_URL")
    # if webhook_url:
    #     httpx.post(webhook_url, json={"text": f"🔴 Ticket #{ticket.id} escalated: {ticket.title}"})


if __name__ == "__main__":
    result = check_and_escalate()
    log.info(f"Result: {result}")
