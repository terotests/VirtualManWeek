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
    last_poll_ts: int = field(default_factory=lambda: int(time.time()))

class Tracker:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.active: Optional[ActiveSession] = None
        models.initialize()
        # Gap / idle handling parameters
        self.max_gap_idle_seconds = 6 * 3600  # cap gap attribution
        self.split_gap_factor = 3            # split session if gap > factor * idle_timeout
        self.auto_split_on_long_gap = True
        # Auto-resume state
        self.resume_mode_label: Optional[str] = None  # original mode before auto Idle
        self.resume_active_start_ts: Optional[int] = None  # when user activity started after idle
        self.restore_active_delay_seconds = 15  # wait this many active seconds before restoring mode
        # Sleep detection tuning
        self.poll_gap_sleep_min = 30   # any gap >= this (seconds) considered a candidate for sleep
        self.poll_gap_log_min = 5      # log gaps >= this for diagnostics
        # Recovery from attributed idle (non-split) state
        self.active_recovery_start: Optional[int] = None  # when continuous activity began after idle attribution

    def start(self, project_id: Optional[int], mode_label: str, description: Optional[str] = None, manual_seconds: int = 0):
        now = int(time.time())
        if self.active:
            self._close(now)
        norm_mode = mode_label.strip()
        models.upsert_mode(norm_mode)
        self.active = ActiveSession(project_id=project_id, mode_label=norm_mode, start_ts=now)
        self._active_description = description
        self._active_manual_seconds = manual_seconds
        # If starting any non-Idle mode, clear pending resume
        if norm_mode.lower() != 'idle':
            self.resume_mode_label = None
            self.resume_active_start_ts = None
        logger.info(f"Start session project={project_id} mode={norm_mode} manual={manual_seconds}s")

    def switch(self, project_id: Optional[int], mode_label: str, description: Optional[str] = None, manual_seconds: int = 0):
        self.start(project_id, mode_label, description, manual_seconds)

    def activity_ping(self):
        if not self.active:
            return
        now = int(time.time())
        sess = self.active
        sess.last_activity_ts = now
        idle_threshold = self.settings.idle_timeout_seconds
        # Auto resume logic: if currently in an auto Idle session and original mode stored
        if sess.mode_label.lower() == 'idle' and self.resume_mode_label:
            if self.resume_active_start_ts is None:
                self.resume_active_start_ts = now
            else:
                if now - self.resume_active_start_ts >= self.restore_active_delay_seconds:
                    orig = self.resume_mode_label
                    logger.info(f"Auto restoring mode '{orig}' after {self.restore_active_delay_seconds}s of activity")
                    self.switch(project_id=None, mode_label=orig, description='(auto resume)')
                    self.resume_mode_label = None
                    self.resume_active_start_ts = None
        # If we stayed in same mode (not switched to Idle placeholder) and just attributed a gap to idle_accum,
        # allow returning to active (clearing idle_accum) after sustained activity window.
        if sess.mode_label.lower() != 'idle' and sess.idle_accum > 0:
            # We are currently marked idle due to accumulated idle_accum but user is active (< idle threshold)
            if now - sess.last_activity_ts < idle_threshold:
                if self.active_recovery_start is None:
                    self.active_recovery_start = now
                elif now - self.active_recovery_start >= self.restore_active_delay_seconds:
                    logger.info(
                        f"Clearing idle_accum ({sess.idle_accum}s) after {self.restore_active_delay_seconds}s sustained activity"
                    )
                    sess.idle_accum = 0
                    self.active_recovery_start = None
            else:
                # User appears idle again, reset recovery window
                self.active_recovery_start = None
        else:
            # Not in a recovery scenario
            self.active_recovery_start = None

    def _check_24_hour_limit(self) -> bool:
        """Check if today's work time has reached 24 hours. If so, stop tracking.
        Returns True if tracking was stopped due to limit."""
        from datetime import datetime
        
        today = datetime.now().strftime("%Y-%m-%d")
        
        with models.connect() as conn:
            cur = conn.cursor()
            # Sum active_seconds and manual_seconds, but exclude idle_seconds
            # Also exclude entries where mode_label is 'Idle' (case-insensitive)
            cur.execute("""
                SELECT COALESCE(SUM(active_seconds), 0) + COALESCE(SUM(manual_seconds), 0)
                FROM time_entries 
                WHERE date = ? AND LOWER(mode_label) != 'idle'
            """, (today,))
            result = cur.fetchone()
            today_work_seconds = result[0] if result and result[0] else 0
        
        # Add current session time if active
        if self.active:
            now = int(time.time())
            session_active_seconds = now - self.active.start_ts - self.active.idle_accum
            today_work_seconds += max(0, session_active_seconds)
        
        # Check if we've reached 24 hours (86400 seconds)
        if today_work_seconds >= 24 * 3600:
            logger.warning("24-hour work limit reached - stopping tracking")
            if self.active:
                self._close(int(time.time()))
            return True
        
        return False

    def poll(self, idle_secs: Optional[int] = None):
        """Periodic maintenance.

        idle_secs: optional externally measured idle (e.g. from GetLastInputInfo). If provided and over
        threshold, we use it rather than just elapsed since last_activity.
        """
        if not self.active:
            return
        
        # Check for 24-hour work limit
        if self._check_24_hour_limit():
            return
            
        now = int(time.time())
        sess = self.active
        idle_threshold = self.settings.idle_timeout_seconds
        gap = now - sess.last_poll_ts
        if gap < 0:
            gap = 0
        if gap >= self.poll_gap_log_min:
            logger.debug(f"poll gap={gap}s idle_accum={sess.idle_accum}s mode={sess.mode_label}")
        # Sleep / long gap detection now uses a lower base threshold so shorter sleeps (< idle_threshold) still detected
        if gap >= self.poll_gap_sleep_min:
            slept = gap >= idle_threshold + 5  # classify as full sleep only if beyond idle threshold
            logger.info(
                f"Detected long poll gap={gap}s (idle_th={idle_threshold}) classify={'sleep' if slept else 'short-sleep'}"
            )
            if slept and self.auto_split_on_long_gap and gap > idle_threshold * self.split_gap_factor:
                original_mode = sess.mode_label if sess.mode_label.lower() != 'idle' else None
                split_end = min(now, sess.last_activity_ts + idle_threshold)
                pre_idle = max(0, split_end - sess.last_activity_ts)
                sess.idle_accum = min(pre_idle, split_end - sess.start_ts)
                logger.info(
                    f"Splitting session at {split_end} (gap {gap}). idle_accum={sess.idle_accum} orig_mode={original_mode}"
                )
                self._close(split_end)
                self.start(project_id=None, mode_label='Idle', description='(auto after resume)')
                if original_mode:
                    self.resume_mode_label = original_mode
                    self.resume_active_start_ts = None
                sess = self.active
            else:
                # Attribute gap as idle (capped). Even for short-sleep classification we add as idle.
                idle_to_add = min(gap, self.max_gap_idle_seconds)
                sess.idle_accum = min((now - sess.start_ts), sess.idle_accum + idle_to_add)
                sess.last_activity_ts = now - min(idle_threshold, idle_to_add)
                logger.info(
                    f"Added gap idle {idle_to_add}s (total idle={sess.idle_accum}s) classify={'sleep' if slept else 'short-sleep'}"
                )
        sess.last_poll_ts = now
        # External idle measurement precedence
        if idle_secs is not None and idle_secs >= idle_threshold:
            sess.idle_accum = min(now - sess.start_ts, idle_secs)
            sess.last_activity_ts = now - idle_secs
        else:
            if now - sess.last_activity_ts >= idle_threshold:
                sess.idle_accum = min(now - sess.start_ts, now - sess.last_activity_ts)

    def stop(self):
        if not self.active:
            return
        self._close(int(time.time()))
        self.active = None

    def flush_all(self):
        if self.active:
            self.stop()

    def _close(self, end_ts: int, manual_seconds: int = 0):
        sess = self.active
        if not sess:
            return
        duration = end_ts - sess.start_ts
        if duration < 10 and self.settings.discard_sub_10s_entries:
            logger.info("Discard short session <10s")
            return
        idle_seconds = min(sess.idle_accum, duration)
        active_seconds = max(0, duration - idle_seconds)
        logger.info(
            f"Close session project={sess.project_id} mode={sess.mode_label} dur={duration}s active={active_seconds}s idle={idle_seconds}s manual={manual_seconds}s"
        )
        # Use manual_seconds from parameter or stored value
        total_manual = manual_seconds or getattr(self, '_active_manual_seconds', 0) or 0
        models.insert_time_entry(
            start_ts=sess.start_ts,
            end_ts=end_ts,
            active_seconds=active_seconds,
            idle_seconds=idle_seconds,
            manual_seconds=total_manual,
            project_id=sess.project_id,
            mode_label=sess.mode_label,
            description=getattr(self, '_active_description', None),
            source="auto",
        )
        self._active_description = None
        self._active_manual_seconds = 0
