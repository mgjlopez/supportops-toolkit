"""
seed.py — Loads 50 realistic sample tickets into SQL Server.

Tickets are generated with realistic distributions:
  - Priorities: ~10% critical, ~25% high, ~40% medium, ~25% low
  - Statuses:   mix of open, in_progress, escalated, resolved, closed
  - Categories: spread across all types
  - Sources:    mostly manual, some auto
  - Ages:       from 5 minutes old to 30 days old

Usage:
    docker compose exec api python db/seed.py
"""

import sys
import os
import random
from datetime import datetime, timedelta, UTC

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from api.database import SessionLocal
from api.models import (
    Ticket, TicketEvent, HealthCheck,
    TicketPriority, TicketStatus, TicketCategory, TicketSource,
)

# ── Realistic ticket templates ────────────────────────────────────────────────

TICKET_TEMPLATES = [
    # Network
    {"title": "VPN disconnecting every 30 minutes for remote team", "category": "network", "priority": "high", "source": "manual", "reporter": "alice.jones", "assignee": "network.team"},
    {"title": "Cannot access shared drive from branch office", "category": "network", "priority": "high", "source": "manual", "reporter": "bob.smith", "assignee": "network.team"},
    {"title": "Wi-Fi dropping on floor 4 — 20 users affected", "category": "network", "priority": "high", "source": "manual", "reporter": "carol.white", "assignee": "network.team"},
    {"title": "Firewall blocking outbound SMTP traffic", "category": "network", "priority": "critical", "source": "auto", "reporter": "health_monitor", "assignee": "network.team"},
    {"title": "DNS resolution failing for internal domains", "category": "network", "priority": "critical", "source": "auto", "reporter": "health_monitor", "assignee": "sysadmin1"},
    {"title": "Latency spike on MPLS link to HQ — 800ms avg", "category": "network", "priority": "high", "source": "auto", "reporter": "health_monitor", "assignee": "network.team"},
    {"title": "Switch CORE-SW-02 port 12 showing errors", "category": "network", "priority": "medium", "source": "manual", "reporter": "it.manager", "assignee": "network.team"},

    # Software
    {"title": "Outlook not syncing — calendar missing for 5 users", "category": "software", "priority": "high", "source": "manual", "reporter": "bob.smith", "assignee": "sysadmin1"},
    {"title": "Excel crashing on open for finance department", "category": "software", "priority": "high", "source": "manual", "reporter": "finance.manager", "assignee": "helpdesk1"},
    {"title": "Teams calls dropping after 10 minutes", "category": "software", "priority": "medium", "source": "manual", "reporter": "hr.director", "assignee": "helpdesk2"},
    {"title": "ERP system slow — page load over 30 seconds", "category": "software", "priority": "high", "source": "manual", "reporter": "ops.manager", "assignee": "sysadmin2"},
    {"title": "Browser extension blocking internal web apps", "category": "software", "priority": "low", "source": "manual", "reporter": "john.doe", "assignee": "helpdesk1"},
    {"title": "Software license renewal — Adobe CC 25 seats", "category": "software", "priority": "low", "source": "manual", "reporter": "it.manager", "assignee": None},
    {"title": "Antivirus definitions not updating on 12 workstations", "category": "software", "priority": "medium", "source": "auto", "reporter": "health_monitor", "assignee": "sysadmin1"},
    {"title": "VoIP softphone not registering after reboot", "category": "software", "priority": "medium", "source": "manual", "reporter": "sales.rep1", "assignee": "helpdesk2"},

    # Hardware
    {"title": "Printer PRTR-FL3 offline — floor 3 team affected", "category": "hardware", "priority": "medium", "source": "manual", "reporter": "mike.chen", "assignee": "field.support"},
    {"title": "Laptop screen flickering — marketing department", "category": "hardware", "priority": "low", "source": "manual", "reporter": "designer1", "assignee": "field.support"},
    {"title": "Server rack UPS beeping — battery health warning", "category": "hardware", "priority": "high", "source": "auto", "reporter": "health_monitor", "assignee": "sysadmin1"},
    {"title": "Workstation failing POST — accounting department", "category": "hardware", "priority": "high", "source": "manual", "reporter": "accountant1", "assignee": "field.support"},
    {"title": "SAN disk showing predictive failure warnings", "category": "hardware", "priority": "critical", "source": "auto", "reporter": "health_monitor", "assignee": "sysadmin1"},
    {"title": "Barcode scanners not connecting via USB on dock", "category": "hardware", "priority": "medium", "source": "manual", "reporter": "warehouse.super", "assignee": "field.support"},
    {"title": "Conference room projector no signal from HDMI", "category": "hardware", "priority": "low", "source": "manual", "reporter": "reception", "assignee": "field.support"},

    # Performance
    {"title": "Disk usage on FILESERVER01 at 91%", "category": "performance", "priority": "critical", "source": "auto", "reporter": "health_monitor", "assignee": None},
    {"title": "CPU usage spike on APP-SERVER-02 — 95% for 20 min", "category": "performance", "priority": "critical", "source": "auto", "reporter": "health_monitor", "assignee": "sysadmin1"},
    {"title": "Remote desktop slow for warehouse team — 800ms latency", "category": "performance", "priority": "medium", "source": "manual", "reporter": "warehouse.super", "assignee": "sysadmin1"},
    {"title": "Database query times degraded after index rebuild", "category": "performance", "priority": "high", "source": "auto", "reporter": "health_monitor", "assignee": "sysadmin2"},
    {"title": "RAM usage on WEB-SERVER-01 at 94%", "category": "performance", "priority": "high", "source": "auto", "reporter": "health_monitor", "assignee": "sysadmin1"},
    {"title": "Backup job taking 14 hours — SLA is 6 hours", "category": "performance", "priority": "medium", "source": "auto", "reporter": "health_monitor", "assignee": "sysadmin2"},
    {"title": "Slow login times — Active Directory response >5s", "category": "performance", "priority": "high", "source": "manual", "reporter": "helpdesk1", "assignee": "sysadmin1"},

    # Access
    {"title": "New hire onboarding — create AD account for Maria Gomez", "category": "access", "priority": "medium", "source": "manual", "reporter": "hr_system", "assignee": "sysadmin2"},
    {"title": "Password reset request — john.murphy locked out", "category": "access", "priority": "low", "source": "manual", "reporter": "john.murphy", "assignee": "helpdesk1"},
    {"title": "MFA not working for CEO on mobile device", "category": "access", "priority": "critical", "source": "manual", "reporter": "executive.assistant", "assignee": "sysadmin1"},
    {"title": "Contractor account access expired — need 30 day extension", "category": "access", "priority": "medium", "source": "manual", "reporter": "project.manager", "assignee": "sysadmin2"},
    {"title": "Shared mailbox permissions not applying correctly", "category": "access", "priority": "medium", "source": "manual", "reporter": "office.admin", "assignee": "helpdesk2"},
    {"title": "VPN certificate expired for 3 remote users", "category": "access", "priority": "high", "source": "auto", "reporter": "health_monitor", "assignee": "sysadmin1"},
    {"title": "Offboarding — revoke all access for Tom Baker", "category": "access", "priority": "high", "source": "manual", "reporter": "hr_system", "assignee": "sysadmin2"},
    {"title": "SharePoint folder permissions broken after migration", "category": "access", "priority": "medium", "source": "manual", "reporter": "team.lead1", "assignee": "sysadmin2"},

    # Security
    {"title": "SSL certificate expiring in 7 days — api.internal.company.com", "category": "security", "priority": "high", "source": "auto", "reporter": "health_monitor", "assignee": "devops.team"},
    {"title": "Suspicious login attempt from unknown IP — 47 failures", "category": "security", "priority": "critical", "source": "auto", "reporter": "health_monitor", "assignee": "sysadmin1"},
    {"title": "Phishing email reported by 8 employees", "category": "security", "priority": "high", "source": "manual", "reporter": "security.awareness", "assignee": "sysadmin1"},
    {"title": "Ransomware alert — endpoint quarantined by AV", "category": "security", "priority": "critical", "source": "auto", "reporter": "health_monitor", "assignee": "sysadmin1"},
    {"title": "USB drive with unknown content found plugged in", "category": "security", "priority": "high", "source": "manual", "reporter": "receptionist", "assignee": "sysadmin1"},
    {"title": "Firewall rule change audit — unauthorized modification detected", "category": "security", "priority": "critical", "source": "auto", "reporter": "health_monitor", "assignee": "network.team"},

    # Other
    {"title": "IT asset inventory update — Q2 audit", "category": "other", "priority": "low", "source": "manual", "reporter": "it.manager", "assignee": None},
    {"title": "Setup new hire workstation — starts Monday", "category": "other", "priority": "medium", "source": "manual", "reporter": "hr_system", "assignee": "field.support"},
    {"title": "Document disaster recovery procedure for SQL Server", "category": "other", "priority": "low", "source": "manual", "reporter": "it.manager", "assignee": "sysadmin2"},
    {"title": "Install approved software on dev team laptops x5", "category": "other", "priority": "low", "source": "manual", "reporter": "dev.manager", "assignee": "field.support"},
    {"title": "Migrate file server data to new NAS — 2TB", "category": "other", "priority": "medium", "source": "manual", "reporter": "it.manager", "assignee": "sysadmin1"},
    {"title": "Monthly patch cycle — 40 servers pending reboot", "category": "other", "priority": "medium", "source": "auto", "reporter": "health_monitor", "assignee": "sysadmin1"},
    {"title": "Procure 10 new laptops for sales team expansion", "category": "other", "priority": "low", "source": "manual", "reporter": "sales.manager", "assignee": None},
]

# Status distribution weights (open/in_progress/escalated/resolved/closed)
STATUS_WEIGHTS = {
    "critical": ["open", "escalated", "escalated", "in_progress", "resolved"],
    "high":     ["open", "open", "in_progress", "in_progress", "resolved"],
    "medium":   ["open", "in_progress", "resolved", "resolved", "closed"],
    "low":      ["open", "resolved", "resolved", "closed", "closed"],
}

SAMPLE_HEALTH_CHECKS = [
    {"target": "http://api:8000/health",         "check_type": "http", "status": "ok",       "value": 200,  "message": "HTTP 200 OK"},
    {"target": "FILESERVER01",                   "check_type": "disk", "status": "critical",  "value": 91.3, "message": "Disk C: at 91.3% — threshold 85%"},
    {"target": "APP-SERVER-02",                  "check_type": "cpu",  "status": "critical",  "value": 95.1, "message": "CPU at 95.1% for 20+ minutes"},
    {"target": "FILESERVER01",                   "check_type": "ram",  "status": "ok",        "value": 67.2, "message": "RAM OK"},
    {"target": "WEB-SERVER-01",                  "check_type": "ram",  "status": "critical",  "value": 94.0, "message": "RAM at 94% — threshold 90%"},
    {"target": "api.internal.company.com:443",   "check_type": "port", "status": "ok",        "value": None, "message": "Port 443 reachable"},
    {"target": "https://httpbin.org/status/200", "check_type": "http", "status": "ok",        "value": 200,  "message": "HTTP 200 OK"},
    {"target": "DB-SERVER-01",                   "check_type": "disk", "status": "warning",   "value": 78.5, "message": "Disk at 78.5% — approaching threshold"},
    {"target": "local",                          "check_type": "cpu",  "status": "ok",        "value": 12.3, "message": "CPU OK"},
    {"target": "local",                          "check_type": "ram",  "status": "ok",        "value": 55.1, "message": "RAM OK"},
]


def seed():
    db = SessionLocal()
    try:
        existing = db.query(Ticket).count()
        if existing > 0:
            print(f"ℹ️  Database already has {existing} tickets. Skipping seed.")
            print("   To re-seed: docker compose down -v && docker compose up -d")
            print("   Then run migrate.py and seed.py again.")
            return

        # Build lookup maps: name → id
        priorities = {r.name: r.id for r in db.query(TicketPriority).all()}
        statuses   = {r.name: r.id for r in db.query(TicketStatus).all()}
        categories = {r.name: r.id for r in db.query(TicketCategory).all()}
        sources    = {r.name: r.id for r in db.query(TicketSource).all()}

        if not priorities:
            print("❌ Lookup tables are empty. Run migrate.py first.")
            return

        print(f"🌱 Seeding {len(TICKET_TEMPLATES)} tickets...")
        now = datetime.now(UTC)

        for i, tmpl in enumerate(TICKET_TEMPLATES):
            # Spread tickets over the last 30 days
            age_hours = random.uniform(0.1, 720)
            created_at = now - timedelta(hours=age_hours)

            # Pick a realistic status based on priority
            status_name = random.choice(STATUS_WEIGHTS[tmpl["priority"]])

            # Resolved/closed tickets get a resolution timestamp
            resolved_at = None
            if status_name in ("resolved", "closed"):
                resolve_delay = random.uniform(0.5, age_hours * 0.8)
                resolved_at = created_at + timedelta(hours=resolve_delay)

            # Some tickets get escalated
            escalated       = status_name == "escalated"
            escalation_count = random.randint(1, 2) if escalated else 0

            # SLA breached for old critical/high open tickets
            sla_hours   = {"critical": 0.25, "high": 1, "medium": 4, "low": 24}
            sla_breached = (
                status_name in ("open", "in_progress", "escalated")
                and age_hours > sla_hours[tmpl["priority"]]
            )

            ticket = Ticket(
                title            = tmpl["title"],
                description      = f"Reported via {tmpl['source']}. Assigned to {tmpl['assignee'] or 'unassigned'}.",
                assignee         = tmpl["assignee"],
                reporter         = tmpl["reporter"],
                escalated        = escalated,
                escalation_count = escalation_count,
                sla_breached     = sla_breached,
                created_at       = created_at,
                updated_at       = created_at,
                resolved_at      = resolved_at,
                priority_id      = priorities[tmpl["priority"]],
                status_id        = statuses[status_name],
                category_id      = categories[tmpl["category"]],
                source_id        = sources[tmpl["source"]],
            )
            db.add(ticket)
            db.flush()

            db.add(TicketEvent(
                ticket_id  = ticket.id,
                event_type = "created",
                message    = f"Ticket created via {tmpl['source']}",
                created_at = created_at,
            ))

            if escalated:
                db.add(TicketEvent(
                    ticket_id  = ticket.id,
                    event_type = "escalated",
                    message    = f"Auto-escalated: SLA breached. Priority: {tmpl['priority']}.",
                    created_at = created_at + timedelta(hours=sla_hours[tmpl["priority"]]),
                ))

            if resolved_at:
                db.add(TicketEvent(
                    ticket_id  = ticket.id,
                    event_type = "resolved",
                    message    = "Ticket resolved and verified with reporter.",
                    created_at = resolved_at,
                ))

        print(f"✅ {len(TICKET_TEMPLATES)} tickets created.")

        print("🌱 Seeding health check log...")
        for hc in SAMPLE_HEALTH_CHECKS:
            for minutes_ago in [random.randint(1, 60) for _ in range(3)]:
                db.add(HealthCheck(
                    target     = hc["target"],
                    check_type = hc["check_type"],
                    status     = hc["status"],
                    value      = hc.get("value"),
                    message    = hc.get("message"),
                    checked_at = now - timedelta(minutes=minutes_ago),
                ))

        db.commit()
        print(f"✅ {len(SAMPLE_HEALTH_CHECKS) * 3} health check entries logged.")
        print("\n🎉 Seed complete! Visit http://localhost:8000/docs to explore the API.")

    except Exception as e:
        db.rollback()
        print(f"❌ Seed failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
