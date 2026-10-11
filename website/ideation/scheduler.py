"""The scheduler — the "continually monitor the internet" part.

A single background thread wakes every `poll_interval_seconds`, runs one cycle
(poll every enabled topic, run a session for any topic that found new signals),
and goes back to sleep. It is fail-safe: an exception in a cycle is recorded and
the loop continues.
"""
import threading
import time
from typing import Any, Dict, Optional


class Scheduler:
    def __init__(self, service, interval_seconds: int):
        self.service = service
        self.interval = max(30, int(interval_seconds))
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.last_cycle: Optional[Dict[str, Any]] = None
        self.last_error: Optional[str] = None
        self.cycles = 0

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="ideation-scheduler", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        # First cycle shortly after start, then every interval.
        if self._stop.wait(5):
            return
        while True:
            self.run_once()
            if self._stop.wait(self.interval):
                return

    def run_once(self) -> Dict[str, Any]:
        try:
            self.last_cycle = self.service.run_cycle(trigger="schedule")
            self.last_error = None
        except Exception as exc:  # noqa: BLE001 - a bad cycle must not kill the loop
            self.last_error = str(exc)
            self.last_cycle = {"error": str(exc)}
        self.cycles += 1
        return self.last_cycle or {}

    def status(self) -> Dict[str, Any]:
        return {
            "running": bool(self._thread and self._thread.is_alive()),
            "interval_seconds": self.interval,
            "cycles": self.cycles,
            "last_cycle": self.last_cycle,
            "last_error": self.last_error,
        }
