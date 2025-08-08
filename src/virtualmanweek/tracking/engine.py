from __future__ import annotations
import time
from dataclasses import dataclass, field
from typing import Optional
from ..config import Settings
from ..utils.logging import get_logger
from ..db import models

logger = get_logger()

@dataclass
class ActiveSession:
    project_id: Optional[int]
    mode_label: str
    start_ts: int
    idle_accum: int = 0
    last_activity_ts: int = field(default_factory=lambda: int(time.time()))

class Tracker:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.active: Optional[ActiveSession] = None
        models.initialize()

    def start(self, project_id: Optional[int], mode_label: str, description: Optional[str] = None):
        now = int(time.time())
        if self.active:
            self._close(now)
        norm_mode = mode_label.strip()
        models.upsert_mode(norm_mode)
        self.active = ActiveSession(project_id=project_id, mode_label=norm_mode, start_ts=now)
        self._active_description = description  # store temporary
        logger.info(f"Start session project={project_id} mode={norm_mode}")

    def switch(self, project_id: Optional[int], mode_label: str, description: Optional[str] = None):
        self.start(project_id, mode_label, description)

    def activity_ping(self):
        if not self.active:
            return
        self.active.last_activity_ts = int(time.time())

    def poll(self):
        if not self.active:
            return
        now = int(time.time())
        idle_threshold = self.settings.idle_timeout_seconds
        if now - self.active.last_activity_ts >= idle_threshold:
            # accumulate idle
            self.active.idle_accum = now - self.active.last_activity_ts

    def stop(self):
        if not self.active:
            return
        self._close(int(time.time()))
        self.active = None

    def flush_all(self):
        if self.active:
            self.stop()

    def _close(self, end_ts: int):
        sess = self.active
        if not sess:
            return
        duration = end_ts - sess.start_ts
        if duration < 10 and self.settings.discard_sub_10s_entries:
            logger.info("Discard short session <10s")
            return
        active_seconds = max(0, duration - sess.idle_accum)
        logger.info(
            f"Close session project={sess.project_id} mode={sess.mode_label} dur={duration}s idle={sess.idle_accum}s"
        )
        models.insert_time_entry(
            start_ts=sess.start_ts,
            end_ts=end_ts,
            active_seconds=active_seconds,
            idle_seconds=sess.idle_accum,
            project_id=sess.project_id,
            mode_label=sess.mode_label,
            description=getattr(self, '_active_description', None),
            source="auto",
        )
        self._active_description = None
