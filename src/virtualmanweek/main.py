from __future__ import annotations
import argparse
import sys
import time
from virtualmanweek.config import Settings
from virtualmanweek.tracking.engine import Tracker
from virtualmanweek.db import models
from virtualmanweek.ui.tray import run_tray


def cli():
    parser = argparse.ArgumentParser(prog="virtualmanweek")
    parser.add_argument("--tray", action="store_true", help="Run system tray UI")
    args = parser.parse_args()
    if args.tray:
        run_tray()
        return
    # default demo
    settings = Settings.load()
    tracker = Tracker(settings)
    # Demo harness: start a session, simulate activity, stop
    project_id = models.upsert_project("GEN", "General")
    tracker.start(project_id, "Initial Setup")
    for _ in range(3):
        time.sleep(1)
        tracker.activity_ping()
        tracker.poll()
    tracker.stop()

if __name__ == "__main__":  # pragma: no cover
    cli()
