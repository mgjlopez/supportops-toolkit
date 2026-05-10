"""
scheduler.py — Runs health_monitor and escalation_engine on configurable intervals.
This is the entrypoint for the 'scheduler' Docker Compose service.

Configure intervals via env vars:
  MONITOR_INTERVAL    — seconds between health check runs (default: 60)
  ESCALATION_INTERVAL — seconds between escalation runs (default: 120)
"""

import os
import sys
import time
import logging

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import schedule

from automation.health_monitor import run_all_checks
from automation.escalation_engine import check_and_escalate

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [Scheduler] %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

MONITOR_INTERVAL = int(os.getenv("MONITOR_INTERVAL", "60"))
ESCALATION_INTERVAL = int(os.getenv("ESCALATION_INTERVAL", "120"))


def main():
    log.info("🚀 SupportOps Scheduler starting up...")
    log.info(f"   Health monitor: every {MONITOR_INTERVAL}s")
    log.info(f"   Escalation engine: every {ESCALATION_INTERVAL}s")

    # Run once immediately on startup
    log.info("Running initial checks...")
    run_all_checks()
    check_and_escalate()

    # Schedule recurring runs
    schedule.every(MONITOR_INTERVAL).seconds.do(run_all_checks)
    schedule.every(ESCALATION_INTERVAL).seconds.do(check_and_escalate)

    log.info("Scheduler running. Press Ctrl+C to stop.")
    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    main()
