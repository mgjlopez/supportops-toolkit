"""
seed.py — Loads 100 realistic sample tickets into SQL Server.

Tickets are generated with realistic distributions:
  - Priorities: ~5% critical, ~15% high, ~50% medium, ~30% low
  - Statuses:   ~50% active (open/in_progress/escalated), ~50% resolved/closed
  - Categories: spread across all types
  - Sources:    mostly manual, some auto
  - Ages:       from 5 minutes old to 36 hours old (yesterday → now)
  - Assignees:  real users and teams from migrate.py

Usage:
    docker compose exec api python db/seed.py           # skips if tickets exist
    docker compose exec api python db/seed.py --force   # wipes tickets and re-seeds
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

# ── Real users & teams from migrate.py ───────────────────────────────────────
# Users:  admin, alice.jones (network.team), bob.smith (sysadmin),
#         carol.white (helpdesk), dave.sec (security),
#         eve.devops (devops), frank.field (field.support)
# Teams:  network.team, sysadmin, helpdesk, security, devops, field.support

TICKET_TEMPLATES = [
    # ── Network (14 tickets) ─────────────────────────────────────────────────
    {"title": "VPN disconnecting every 30 minutes for remote team",              "category": "network",     "priority": "medium",   "source": "manual", "reporter": "carol.white",   "assignee": "alice.jones"},
    {"title": "Cannot access shared drive from branch office",                   "category": "network",     "priority": "medium",   "source": "manual", "reporter": "bob.smith",     "assignee": "network.team"},
    {"title": "Wi-Fi dropping intermittently on floor 4",                        "category": "network",     "priority": "medium",   "source": "manual", "reporter": "frank.field",   "assignee": "alice.jones"},
    {"title": "Firewall blocking outbound SMTP traffic",                         "category": "network",     "priority": "high",     "source": "auto",   "reporter": "health_monitor", "assignee": "network.team"},
    {"title": "DNS resolution slow for internal domains — >3s response",         "category": "network",     "priority": "medium",   "source": "auto",   "reporter": "health_monitor", "assignee": "alice.jones"},
    {"title": "Latency spike on MPLS link to HQ — 400ms avg",                   "category": "network",     "priority": "medium",   "source": "auto",   "reporter": "health_monitor", "assignee": "network.team"},
    {"title": "Switch CORE-SW-02 port 12 showing intermittent errors",          "category": "network",     "priority": "low",      "source": "manual", "reporter": "admin",          "assignee": "alice.jones"},
    {"title": "Wireless access point AP-FL2-03 offline",                         "category": "network",     "priority": "low",      "source": "manual", "reporter": "carol.white",   "assignee": "network.team"},
    {"title": "Network cable replacement needed — meeting room B",               "category": "network",     "priority": "low",      "source": "manual", "reporter": "frank.field",   "assignee": "alice.jones"},
    {"title": "Guest Wi-Fi password rotation due",                               "category": "network",     "priority": "low",      "source": "manual", "reporter": "admin",          "assignee": "network.team"},
    {"title": "VLAN misconfiguration on new switch — floor 2",                  "category": "network",     "priority": "medium",   "source": "manual", "reporter": "alice.jones",   "assignee": "network.team"},
    {"title": "Network printer PRNT-NET-01 unreachable from subnet 10.2.x",     "category": "network",     "priority": "low",      "source": "manual", "reporter": "carol.white",   "assignee": "alice.jones"},
    {"title": "Bandwidth usage spike on WAN link — investigate cause",           "category": "network",     "priority": "medium",   "source": "auto",   "reporter": "health_monitor", "assignee": "network.team"},
    {"title": "Remote office VPN tunnel flapping — 3 reconnects/hour",          "category": "network",     "priority": "medium",   "source": "auto",   "reporter": "health_monitor", "assignee": "alice.jones"},

    # ── Software (18 tickets) ────────────────────────────────────────────────
    {"title": "Outlook not syncing calendar for 3 users after update",          "category": "software",    "priority": "medium",   "source": "manual", "reporter": "alice.jones",   "assignee": "bob.smith"},
    {"title": "Excel freezing when opening files larger than 10MB",             "category": "software",    "priority": "medium",   "source": "manual", "reporter": "frank.field",   "assignee": "carol.white"},
    {"title": "Teams calls dropping audio after 15 minutes",                    "category": "software",    "priority": "medium",   "source": "manual", "reporter": "eve.devops",    "assignee": "helpdesk"},
    {"title": "ERP system page load degraded — averaging 12 seconds",          "category": "software",    "priority": "medium",   "source": "manual", "reporter": "admin",          "assignee": "bob.smith"},
    {"title": "Browser extension blocking internal portal on Chrome 124",       "category": "software",    "priority": "low",      "source": "manual", "reporter": "frank.field",   "assignee": "carol.white"},
    {"title": "Software license renewal — Adobe CC 25 seats expiring next month","category": "software",   "priority": "low",      "source": "manual", "reporter": "admin",          "assignee": None},
    {"title": "Antivirus definitions not updating on 6 workstations",           "category": "software",    "priority": "medium",   "source": "auto",   "reporter": "health_monitor", "assignee": "bob.smith"},
    {"title": "VoIP softphone not registering after workstation reboot",        "category": "software",    "priority": "medium",   "source": "manual", "reporter": "alice.jones",   "assignee": "helpdesk"},
    {"title": "PDF printer driver missing after Windows update",                "category": "software",    "priority": "low",      "source": "manual", "reporter": "carol.white",   "assignee": "helpdesk"},
    {"title": "Slack desktop app crashing on startup — 4 users",               "category": "software",    "priority": "low",      "source": "manual", "reporter": "eve.devops",    "assignee": "carol.white"},
    {"title": "Remote desktop client version mismatch after server upgrade",    "category": "software",    "priority": "medium",   "source": "manual", "reporter": "bob.smith",     "assignee": "sysadmin"},
    {"title": "Zoom plugin not loading in Outlook calendar",                    "category": "software",    "priority": "low",      "source": "manual", "reporter": "frank.field",   "assignee": "helpdesk"},
    {"title": "Windows 11 upgrade compatibility check — 40 devices",           "category": "software",    "priority": "low",      "source": "manual", "reporter": "admin",          "assignee": "bob.smith"},
    {"title": "Shared mailbox not appearing in Outlook after permissions set",  "category": "software",    "priority": "medium",   "source": "manual", "reporter": "carol.white",   "assignee": "helpdesk"},
    {"title": "macOS Sonoma update breaking VPN client — 5 users",             "category": "software",    "priority": "medium",   "source": "manual", "reporter": "eve.devops",    "assignee": "bob.smith"},
    {"title": "PowerBI report not refreshing — data source credentials expired","category": "software",   "priority": "medium",   "source": "manual", "reporter": "alice.jones",   "assignee": "helpdesk"},
    {"title": "AutoCAD license server unreachable from design workstations",    "category": "software",    "priority": "high",     "source": "manual", "reporter": "frank.field",   "assignee": "bob.smith"},
    {"title": "ERP nightly sync job failed — 3 consecutive nights",            "category": "software",    "priority": "high",     "source": "auto",   "reporter": "health_monitor", "assignee": "bob.smith"},

    # ── Hardware (14 tickets) ────────────────────────────────────────────────
    {"title": "Printer PRTR-FL3 offline — floor 3 team affected",              "category": "hardware",    "priority": "medium",   "source": "manual", "reporter": "carol.white",   "assignee": "frank.field"},
    {"title": "Laptop screen flickering — 2 units in marketing",               "category": "hardware",    "priority": "low",      "source": "manual", "reporter": "eve.devops",    "assignee": "field.support"},
    {"title": "Server rack UPS battery health warning — runtime <10min",       "category": "hardware",    "priority": "medium",   "source": "auto",   "reporter": "health_monitor", "assignee": "bob.smith"},
    {"title": "Workstation failing POST — accounting department",               "category": "hardware",    "priority": "high",     "source": "manual", "reporter": "carol.white",   "assignee": "frank.field"},
    {"title": "SAN disk showing SMART predictive failure warnings — disk 4",   "category": "hardware",    "priority": "high",     "source": "auto",   "reporter": "health_monitor", "assignee": "bob.smith"},
    {"title": "Barcode scanners not pairing via Bluetooth on new dock",        "category": "hardware",    "priority": "medium",   "source": "manual", "reporter": "frank.field",   "assignee": "field.support"},
    {"title": "Conference room projector no signal from HDMI — room 3B",       "category": "hardware",    "priority": "low",      "source": "manual", "reporter": "alice.jones",   "assignee": "frank.field"},
    {"title": "Keyboard and mouse unresponsive on reception workstation",       "category": "hardware",    "priority": "low",      "source": "manual", "reporter": "carol.white",   "assignee": "field.support"},
    {"title": "Monitor display flickering on second screen — dev team",         "category": "hardware",    "priority": "low",      "source": "manual", "reporter": "eve.devops",    "assignee": "field.support"},
    {"title": "Laptop battery not charging — 3 devices flagged this week",     "category": "hardware",    "priority": "low",      "source": "manual", "reporter": "frank.field",   "assignee": "field.support"},
    {"title": "Webcam not detected in Teams/Zoom — 4 remote workers",         "category": "hardware",    "priority": "medium",   "source": "manual", "reporter": "carol.white",   "assignee": "helpdesk"},
    {"title": "Label printer PLT-WH-01 paper jam — warehouse team",            "category": "hardware",    "priority": "medium",   "source": "manual", "reporter": "frank.field",   "assignee": "frank.field"},
    {"title": "Docking station not detecting external monitors — 2 laptops",   "category": "hardware",    "priority": "low",      "source": "manual", "reporter": "eve.devops",    "assignee": "field.support"},
    {"title": "Network switch port 8 physical damage — needs replacement",     "category": "hardware",    "priority": "medium",   "source": "manual", "reporter": "alice.jones",   "assignee": "network.team"},

    # ── Performance (12 tickets) ─────────────────────────────────────────────
    {"title": "Disk usage on FILESERVER01 at 87% — cleanup needed",           "category": "performance", "priority": "medium",   "source": "auto",   "reporter": "health_monitor", "assignee": "bob.smith"},
    {"title": "CPU usage elevated on APP-SERVER-02 — 78% sustained",          "category": "performance", "priority": "medium",   "source": "auto",   "reporter": "health_monitor", "assignee": "bob.smith"},
    {"title": "Remote desktop slow for warehouse team — 400ms latency",        "category": "performance", "priority": "medium",   "source": "manual", "reporter": "frank.field",   "assignee": "sysadmin"},
    {"title": "Database query times degraded after index rebuild",             "category": "performance", "priority": "medium",   "source": "auto",   "reporter": "health_monitor", "assignee": "bob.smith"},
    {"title": "RAM usage on WEB-SERVER-01 at 86%",                            "category": "performance", "priority": "medium",   "source": "auto",   "reporter": "health_monitor", "assignee": "sysadmin"},
    {"title": "Backup job taking 9 hours — SLA is 6 hours",                   "category": "performance", "priority": "medium",   "source": "auto",   "reporter": "health_monitor", "assignee": "bob.smith"},
    {"title": "Slow login times — Active Directory response 3–5s",            "category": "performance", "priority": "medium",   "source": "manual", "reporter": "carol.white",   "assignee": "bob.smith"},
    {"title": "File server response slow during business hours — I/O wait",   "category": "performance", "priority": "low",      "source": "auto",   "reporter": "health_monitor", "assignee": "bob.smith"},
    {"title": "VM DEVBOX-03 swap usage at 60% — memory pressure",             "category": "performance", "priority": "low",      "source": "auto",   "reporter": "health_monitor", "assignee": "eve.devops"},
    {"title": "Nightly report generation taking 2x longer than baseline",     "category": "performance", "priority": "low",      "source": "manual", "reporter": "admin",          "assignee": "bob.smith"},
    {"title": "SAN IOPS degraded after firmware update — 30% throughput drop","category": "performance", "priority": "high",     "source": "auto",   "reporter": "health_monitor", "assignee": "bob.smith"},
    {"title": "DHCP lease pool nearly exhausted — 92% used",                  "category": "performance", "priority": "high",     "source": "auto",   "reporter": "health_monitor", "assignee": "alice.jones"},

    # ── Access (16 tickets) ──────────────────────────────────────────────────
    {"title": "New hire onboarding — create AD account for Maria Gomez",       "category": "access",      "priority": "medium",   "source": "manual", "reporter": "admin",          "assignee": "bob.smith"},
    {"title": "Password reset request — john.murphy locked out",               "category": "access",      "priority": "low",      "source": "manual", "reporter": "carol.white",   "assignee": "helpdesk"},
    {"title": "MFA enrollment failing on iOS for 2 users",                    "category": "access",      "priority": "medium",   "source": "manual", "reporter": "admin",          "assignee": "bob.smith"},
    {"title": "Contractor account access expired — need 30-day extension",     "category": "access",      "priority": "medium",   "source": "manual", "reporter": "alice.jones",   "assignee": "carol.white"},
    {"title": "Shared mailbox permissions not applying correctly",             "category": "access",      "priority": "medium",   "source": "manual", "reporter": "frank.field",   "assignee": "helpdesk"},
    {"title": "VPN certificate expiring in 14 days — 5 remote users",         "category": "access",      "priority": "medium",   "source": "auto",   "reporter": "health_monitor", "assignee": "alice.jones"},
    {"title": "Offboarding — revoke all access for Tom Baker",                 "category": "access",      "priority": "medium",   "source": "manual", "reporter": "admin",          "assignee": "bob.smith"},
    {"title": "SharePoint folder permissions broken after site migration",     "category": "access",      "priority": "medium",   "source": "manual", "reporter": "eve.devops",    "assignee": "carol.white"},
    {"title": "User sarah.lee cannot log in after name change in AD",          "category": "access",      "priority": "medium",   "source": "manual", "reporter": "carol.white",   "assignee": "helpdesk"},
    {"title": "Distribution list not receiving external emails",               "category": "access",      "priority": "low",      "source": "manual", "reporter": "alice.jones",   "assignee": "helpdesk"},
    {"title": "New hire onboarding — Ryan Park, starts 2026-06-03",           "category": "access",      "priority": "low",      "source": "manual", "reporter": "admin",          "assignee": "bob.smith"},
    {"title": "Reset expired service account password — svc_backup",          "category": "access",      "priority": "medium",   "source": "auto",   "reporter": "health_monitor", "assignee": "bob.smith"},
    {"title": "Temp contractor needs read-only access to SharePoint projects", "category": "access",      "priority": "low",      "source": "manual", "reporter": "alice.jones",   "assignee": "carol.white"},
    {"title": "Group policy not applying to new OU after AD restructure",      "category": "access",      "priority": "medium",   "source": "manual", "reporter": "bob.smith",     "assignee": "sysadmin"},
    {"title": "Teams channel access request — external partner onboarding",    "category": "access",      "priority": "low",      "source": "manual", "reporter": "admin",          "assignee": "helpdesk"},
    {"title": "Drive mapping broken after server migration — finance team",    "category": "access",      "priority": "medium",   "source": "manual", "reporter": "carol.white",   "assignee": "bob.smith"},

    # ── Security (12 tickets) ────────────────────────────────────────────────
    {"title": "SSL certificate expiring in 21 days — api.internal.company.com","category": "security",   "priority": "medium",   "source": "auto",   "reporter": "health_monitor", "assignee": "eve.devops"},
    {"title": "Suspicious login from new country — user alice.jones",         "category": "security",    "priority": "medium",   "source": "auto",   "reporter": "health_monitor", "assignee": "dave.sec"},
    {"title": "Phishing email reported by 3 employees — link blocked",        "category": "security",    "priority": "medium",   "source": "manual", "reporter": "carol.white",   "assignee": "security"},
    {"title": "Malware detected on workstation WS-MKT-14 — quarantined",     "category": "security",    "priority": "high",     "source": "auto",   "reporter": "health_monitor", "assignee": "dave.sec"},
    {"title": "USB drive with unknown content found — reception desk",        "category": "security",    "priority": "medium",   "source": "manual", "reporter": "frank.field",   "assignee": "dave.sec"},
    {"title": "Firewall rule audit — 3 rules flagged for review",             "category": "security",    "priority": "medium",   "source": "manual", "reporter": "dave.sec",      "assignee": "security"},
    {"title": "Failed SSH login attempts on JUMP-SERVER-01 — 15 in 1h",      "category": "security",    "priority": "medium",   "source": "auto",   "reporter": "health_monitor", "assignee": "dave.sec"},
    {"title": "Internal SSL cert expiring — intranet.company.local",          "category": "security",    "priority": "low",      "source": "auto",   "reporter": "health_monitor", "assignee": "eve.devops"},
    {"title": "User downloaded unapproved software — policy reminder needed", "category": "security",    "priority": "low",      "source": "manual", "reporter": "dave.sec",      "assignee": "security"},
    {"title": "Security awareness training completion below 80% — reminder",  "category": "security",    "priority": "low",      "source": "manual", "reporter": "admin",          "assignee": "dave.sec"},
    {"title": "Privileged account quarterly access review due",               "category": "security",    "priority": "medium",   "source": "manual", "reporter": "admin",          "assignee": "dave.sec"},
    {"title": "CVE-2025-1234 patch not yet applied — 8 servers affected",     "category": "security",    "priority": "high",     "source": "auto",   "reporter": "health_monitor", "assignee": "bob.smith"},

    # ── Other (14 tickets) ───────────────────────────────────────────────────
    {"title": "IT asset inventory update — Q2 2026 audit",                    "category": "other",       "priority": "low",      "source": "manual", "reporter": "admin",          "assignee": None},
    {"title": "Setup new hire workstation — Ryan Park, starts Monday",        "category": "other",       "priority": "medium",   "source": "manual", "reporter": "admin",          "assignee": "frank.field"},
    {"title": "Document disaster recovery procedure for SQL Server 2025",     "category": "other",       "priority": "low",      "source": "manual", "reporter": "bob.smith",     "assignee": "eve.devops"},
    {"title": "Install approved software on dev team laptops — 5 units",     "category": "other",       "priority": "low",      "source": "manual", "reporter": "eve.devops",    "assignee": "frank.field"},
    {"title": "Migrate file server data to new NAS — 2TB",                   "category": "other",       "priority": "medium",   "source": "manual", "reporter": "admin",          "assignee": "bob.smith"},
    {"title": "Monthly patch cycle — 40 servers pending reboot",              "category": "other",       "priority": "medium",   "source": "auto",   "reporter": "health_monitor", "assignee": "sysadmin"},
    {"title": "Procure 10 new laptops for sales team expansion",              "category": "other",       "priority": "low",      "source": "manual", "reporter": "admin",          "assignee": None},
    {"title": "Decommission legacy server SRV-OLD-02",                        "category": "other",       "priority": "low",      "source": "manual", "reporter": "bob.smith",     "assignee": "eve.devops"},
    {"title": "Update IT onboarding checklist for 2026",                      "category": "other",       "priority": "low",      "source": "manual", "reporter": "admin",          "assignee": "carol.white"},
    {"title": "Reconfigure meeting room AV setup — room 4A renovation",       "category": "other",       "priority": "medium",   "source": "manual", "reporter": "frank.field",   "assignee": "frank.field"},
    {"title": "Vendor review — renew managed AV contract or switch provider", "category": "other",       "priority": "low",      "source": "manual", "reporter": "admin",          "assignee": None},
    {"title": "Create runbook for AD password reset procedure",               "category": "other",       "priority": "low",      "source": "manual", "reporter": "bob.smith",     "assignee": "carol.white"},
    {"title": "Evaluate ticketing system upgrade — ServiceNow vs Jira SM",   "category": "other",       "priority": "low",      "source": "manual", "reporter": "admin",          "assignee": None},
    {"title": "Quarterly IT spend report — Q1 2026 actuals",                 "category": "other",       "priority": "low",      "source": "manual", "reporter": "admin",          "assignee": None},
]

# Priority distribution check (informational):
# critical: 0, high: ~10%, medium: ~55%, low: ~35%

# Status weights tuned to produce ~50% active / ~50% resolved across all priorities
# active  = open | in_progress | escalated
# resolved = resolved | closed
STATUS_WEIGHTS = {
    "critical": ["open", "escalated", "in_progress", "resolved", "resolved"],
    "high":     ["open", "in_progress", "resolved", "resolved", "closed"],
    "medium":   ["open", "in_progress", "resolved", "resolved", "closed"],
    "low":      ["in_progress", "resolved", "resolved", "closed", "closed"],
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


def seed(force: bool = False):
    db = SessionLocal()
    try:
        existing = db.query(Ticket).count()
        if existing > 0:
            if not force:
                print(f"ℹ️  Database already has {existing} tickets. Skipping seed.")
                print("   To re-seed without losing users/lookups, run:")
                print("   docker compose exec api python db/seed.py --force")
                return
            print(f"⚠️  --force: deleting {existing} existing tickets and health checks...")
            db.query(HealthCheck).delete()
            db.query(Ticket).delete()
            db.commit()
            print("   Cleared. Re-seeding now...")

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
            # Spread tickets between 5 minutes ago and 36 hours ago (yesterday to now)
            age_hours = random.uniform(0.08, 36)
            created_at = now - timedelta(hours=age_hours)

            # Pick a realistic status based on priority
            status_name = random.choice(STATUS_WEIGHTS[tmpl["priority"]])

            # Resolved/closed tickets get a resolution timestamp
            resolved_at = None
            if status_name in ("resolved", "closed"):
                resolve_delay = random.uniform(0.5, max(0.6, age_hours * 0.8))
                resolved_at = created_at + timedelta(hours=resolve_delay)

            # Some tickets get escalated
            escalated        = status_name == "escalated"
            escalation_count = random.randint(1, 2) if escalated else 0

            # SLA breached for open tickets older than their SLA threshold
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
        # Expected: ~50 active (open/in_progress/escalated), ~50 resolved/closed

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
    force = "--force" in sys.argv
    seed(force=force)
