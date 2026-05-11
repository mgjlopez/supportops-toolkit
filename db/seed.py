"""
seed.py — Loads realistic sample data into SQL Server.

Resolves lookup IDs automatically so ticket creation uses
the normalized foreign keys instead of plain text fields.

Usage:
    docker compose exec api python db/seed.py
"""

import sys
import os
import random
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from api.database import SessionLocal
from api.models import (
    Ticket, TicketEvent, HealthCheck,
    TicketPriority, TicketStatus, TicketCategory, TicketSource,
)

SAMPLE_TICKETS = [
    {
        "title": "VPN disconnecting every 30 minutes for remote team",
        "description": "Multiple users report VPN drops. Affects Sydney and London offices.",
        "priority": "high", "category": "network", "status": "open",
        "reporter": "alice.jones", "assignee": "network.team", "source": "manual",
        "age_hours": 3,
    },
    {
        "title": "Outlook not syncing — calendar missing for 5 users",
        "description": "After yesterday's Exchange update, 5 users lost calendar sync.",
        "priority": "high", "category": "software", "status": "in_progress",
        "reporter": "bob.smith", "assignee": "sysadmin1", "source": "manual",
        "age_hours": 6,
    },
    {
        "title": "Disk usage on FILESERVER01 at 91%",
        "description": "Automated alert: disk C: at 91.3%. Threshold is 85%.",
        "priority": "critical", "category": "performance", "status": "open",
        "reporter": "health_monitor", "assignee": None, "source": "auto",
        "age_hours": 0.5, "sla_breached": True,
    },
    {
        "title": "New hire onboarding — create AD account for Maria Gomez",
        "description": "Start date: next Monday. Department: Finance. Manager: carlos.ruiz",
        "priority": "medium", "category": "access", "status": "resolved",
        "reporter": "hr_system", "assignee": "sysadmin2", "source": "manual",
        "age_hours": 48, "resolved_hours_ago": 24,
    },
    {
        "title": "Printer PRTR-FL3 offline — floor 3 team affected",
        "description": "HP LaserJet on floor 3 shows offline since 9am. Affecting 12 users.",
        "priority": "medium", "category": "hardware", "status": "in_progress",
        "reporter": "mike.chen", "assignee": "field.support", "source": "manual",
        "age_hours": 4,
    },
    {
        "title": "SSL certificate expiring in 7 days — api.internal.company.com",
        "description": "Automated check detected cert expiry on 2024-12-15.",
        "priority": "high", "category": "security", "status": "open",
        "reporter": "health_monitor", "assignee": "devops.team", "source": "auto",
        "age_hours": 2,
    },
    {
        "title": "Remote desktop slow for warehouse team",
        "description": "RDS session latency 800ms+. Affects barcode scanner workflow.",
        "priority": "medium", "category": "performance", "status": "resolved",
        "reporter": "warehouse.supervisor", "assignee": "sysadmin1", "source": "manual",
        "age_hours": 72, "resolved_hours_ago": 48,
    },
    {
        "title": "Password reset request — john.murphy locked out",
        "description": "Account locked after 5 failed attempts. User traveling.",
        "priority": "low", "category": "access", "status": "resolved",
        "reporter": "john.murphy", "assignee": "helpdesk1", "source": "manual",
        "age_hours": 24, "resolved_hours_ago": 23,
    },
    {
        "title": "CPU usage spike on APP-SERVER-02 — 95% for 20 min",
        "description": "Health monitor detected sustained CPU spike. Java process suspicious.",
        "priority": "critical", "category": "performance", "status": "escalated",
        "reporter": "health_monitor", "assignee": "sysadmin1", "source": "auto",
        "age_hours": 1, "escalated": True, "escalation_count": 1, "sla_breached": True,
    },
    {
        "title": "Software license renewal — Adobe CC 25 seats",
        "description": "Current license expires in 30 days. Need procurement approval.",
        "priority": "low", "category": "software", "status": "open",
        "reporter": "it.manager", "assignee": None, "source": "manual",
        "age_hours": 120,
    },
]

SAMPLE_HEALTH_CHECKS = [
    {"target": "http://api:8000/health",          "check_type": "http", "status": "ok",       "value": 200,  "message": "HTTP 200 OK"},
    {"target": "FILESERVER01",                    "check_type": "disk", "status": "critical",  "value": 91.3, "message": "Disk C: at 91.3% — threshold 85%"},
    {"target": "APP-SERVER-02",                   "check_type": "cpu",  "status": "critical",  "value": 95.1, "message": "CPU at 95.1% for 20+ minutes"},
    {"target": "FILESERVER01",                    "check_type": "ram",  "status": "ok",        "value": 67.2, "message": "RAM OK"},
    {"target": "api.internal.company.com:443",    "check_type": "port", "status": "ok",        "value": None, "message": "Port 443 reachable"},
    {"target": "https://httpbin.org/status/200",  "check_type": "http", "status": "ok",        "value": 200,  "message": "HTTP 200 OK"},
]


def seed():
    db = SessionLocal()
    try:
        existing = db.query(Ticket).count()
        if existing > 0:
            print(f"ℹ️  Database already has {existing} tickets. Skipping seed.")
            return

        # Build lookup maps: name → id
        priorities = {r.name: r.id for r in db.query(TicketPriority).all()}
        statuses   = {r.name: r.id for r in db.query(TicketStatus).all()}
        categories = {r.name: r.id for r in db.query(TicketCategory).all()}
        sources    = {r.name: r.id for r in db.query(TicketSource).all()}

        if not priorities:
            print("❌ Lookup tables are empty. Run migrate.py first.")
            return

        print("🌱 Seeding sample tickets...")
        now = datetime.utcnow()

        for data in SAMPLE_TICKETS:
            age               = data.pop("age_hours", 0)
            resolved_hours_ago = data.pop("resolved_hours_ago", None)
            created_at        = now - timedelta(hours=age)
            resolved_at       = now - timedelta(hours=resolved_hours_ago) if resolved_hours_ago else None

            ticket = Ticket(
                title            = data["title"],
                description      = data.get("description"),
                assignee         = data.get("assignee"),
                reporter         = data.get("reporter"),
                escalated        = data.get("escalated", False),
                escalation_count = data.get("escalation_count", 0),
                sla_breached     = data.get("sla_breached", False),
                created_at       = created_at,
                updated_at       = created_at,
                resolved_at      = resolved_at,
                priority_id      = priorities[data["priority"]],
                status_id        = statuses[data["status"]],
                category_id      = categories[data["category"]],
                source_id        = sources[data["source"]],
            )
            db.add(ticket)
            db.flush()

            db.add(TicketEvent(
                ticket_id  = ticket.id,
                event_type = "created",
                message    = f"Ticket seeded (source: {data['source']})",
                created_at = created_at,
            ))
            if resolved_at:
                db.add(TicketEvent(
                    ticket_id  = ticket.id,
                    event_type = "resolved",
                    message    = "Ticket resolved",
                    created_at = resolved_at,
                ))

        print(f"✅ {len(SAMPLE_TICKETS)} tickets created.")

        print("🌱 Seeding health check log...")
        for hc in SAMPLE_HEALTH_CHECKS:
            db.add(HealthCheck(
                target     = hc["target"],
                check_type = hc["check_type"],
                status     = hc["status"],
                value      = hc.get("value"),
                message    = hc.get("message"),
                checked_at = now - timedelta(minutes=random.randint(1, 30)),
            ))

        db.commit()
        print(f"✅ {len(SAMPLE_HEALTH_CHECKS)} health checks logged.")
        print("\n🎉 Seed complete! Visit http://localhost:8000/docs to explore the API.")

    except Exception as e:
        db.rollback()
        print(f"❌ Seed failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
