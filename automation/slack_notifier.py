"""
slack_notifier.py — Slack webhook integration for SupportOps alerts.

Sends structured Block Kit messages to a Slack channel when:
  - A critical or high ticket is auto-created by the health monitor
  - A ticket is SLA-breached for the first time
  - A ticket is escalated by the escalation engine

Configuration:
    Set SLACK_WEBHOOK_URL in your .env file.
    If the variable is missing or empty, all notifications are silently skipped.

Usage:
    from automation.slack_notifier import notify_new_ticket, notify_sla_breach, notify_escalation
"""

import os
import httpx
from api.logger import get_logger

log = get_logger(__name__)

SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")

PRIORITY_EMOJI = {
    "critical": "🔴",
    "high":     "🟠",
    "medium":   "🟡",
    "low":      "🟢",
}

PRIORITY_COLOR = {
    "critical": "#f87171",
    "high":     "#fb923c",
    "medium":   "#fbbf24",
    "low":      "#34d399",
}


def _send(payload: dict) -> bool:
    """POST a Block Kit payload to the configured Slack webhook. Returns True on success."""
    if not SLACK_WEBHOOK_URL:
        log.debug("Slack webhook not configured — skipping notification")
        return False
    try:
        resp = httpx.post(SLACK_WEBHOOK_URL, json=payload, timeout=8)
        if resp.status_code == 200 and resp.text == "ok":
            log.info("Slack notification sent")
            return True
        log.warning("Slack webhook returned unexpected response",
                    extra={"status": resp.status_code, "body": resp.text[:100]})
    except Exception as e:
        log.error("Slack notification failed", extra={"error": str(e)})
    return False


def _divider():
    return {"type": "divider"}


def _section(text: str):
    return {"type": "section", "text": {"type": "mrkdwn", "text": text}}


def _fields(*pairs):
    """pairs = list of (label, value) tuples, rendered as two-column fields."""
    return {
        "type": "section",
        "fields": [
            {"type": "mrkdwn", "text": f"*{label}*\n{value}"}
            for label, value in pairs
        ],
    }


def _context(text: str):
    return {"type": "context", "elements": [{"type": "mrkdwn", "text": text}]}


# ── Public API ────────────────────────────────────────────────────────────────

def notify_new_ticket(ticket_id: int, title: str, priority: str,
                      category: str, assignee: str | None = None) -> bool:
    """
    Alert sent when the health monitor auto-creates a critical or high ticket.
    Only fires for critical/high — medium and low are intentionally suppressed.
    """
    if priority not in ("critical", "high"):
        return False

    emoji = PRIORITY_EMOJI.get(priority, "⚪")
    color = PRIORITY_COLOR.get(priority, "#6b7280")

    payload = {
        "attachments": [
            {
                "color": color,
                "blocks": [
                    _section(f"{emoji} *New {priority.upper()} ticket auto-created*"),
                    _divider(),
                    _section(f"*#{ticket_id} — {title}*"),
                    _fields(
                        ("Priority",  f"{emoji} {priority.capitalize()}"),
                        ("Category",  category.capitalize()),
                        ("Assignee",  assignee or "_Unassigned_"),
                        ("Source",    "🤖 Health Monitor"),
                    ),
                    _context("SupportOps Toolkit · Health Monitor"),
                ],
            }
        ]
    }
    return _send(payload)


def notify_sla_breach(ticket_id: int, title: str, priority: str,
                      age_hours: float, sla_hours: float,
                      assignee: str | None = None) -> bool:
    """
    Alert sent the first time a ticket's SLA is marked as breached.
    Fires for all priorities.
    """
    emoji     = PRIORITY_EMOJI.get(priority, "⚪")
    over_by   = age_hours - sla_hours
    over_str  = f"{over_by:.1f}h over SLA"

    payload = {
        "attachments": [
            {
                "color": "#f87171",   # always red for SLA breach
                "blocks": [
                    _section(f"⚠️ *SLA Breach detected*"),
                    _divider(),
                    _section(f"*#{ticket_id} — {title}*"),
                    _fields(
                        ("Priority",   f"{emoji} {priority.capitalize()}"),
                        ("SLA limit",  f"{sla_hours}h"),
                        ("Ticket age", f"{age_hours:.1f}h ({over_str})"),
                        ("Assignee",   assignee or "_Unassigned_"),
                    ),
                    _context("SupportOps Toolkit · Escalation Engine"),
                ],
            }
        ]
    }
    return _send(payload)


def notify_escalation(ticket_id: int, title: str, priority: str,
                      escalation_count: int, age_hours: float,
                      assignee: str | None = None) -> bool:
    """
    Alert sent each time a ticket is escalated by the escalation engine.
    """
    emoji = PRIORITY_EMOJI.get(priority, "⚪")

    payload = {
        "attachments": [
            {
                "color": PRIORITY_COLOR.get(priority, "#6b7280"),
                "blocks": [
                    _section(f"⏫ *Ticket escalated* (#{escalation_count})"),
                    _divider(),
                    _section(f"*#{ticket_id} — {title}*"),
                    _fields(
                        ("Priority",          f"{emoji} {priority.capitalize()}"),
                        ("Escalation count",  str(escalation_count)),
                        ("Ticket age",        f"{age_hours:.1f}h"),
                        ("Assignee",          assignee or "_Unassigned_"),
                    ),
                    _context("SupportOps Toolkit · Escalation Engine"),
                ],
            }
        ]
    }
    return _send(payload)
