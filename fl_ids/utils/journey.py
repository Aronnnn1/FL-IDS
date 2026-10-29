"""Stage timing for an end-to-end run: which stage a run is in, and how long each took.

A `Journey` logs every stage as it starts and ends, and (given a path)
rewrites a small JSON file after each change, so a run can be followed
while it runs (`current_stage`, `detail`) and timed afterwards
(`start_s`, `duration_s` per stage, seconds from the journey's start).
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


class Journey:
    """Times the stages of one run.

    Args:
        name: Run name, used in log lines and the JSON (e.g. "phase_a").
        stages: Planned stage labels, in order; `stage()` labels should
            come from this list so "stage i/n" is meaningful.
        path: If given, the JSON is rewritten here after every change.
    """

    def __init__(self, name: str, stages: list[str], path: str | Path | None = None) -> None:
        self.name = name
        self.planned = list(stages)
        self.path = Path(path) if path else None
        self.started_at = datetime.now(timezone.utc).isoformat()
        self._t0 = time.monotonic()
        self.stages: list[dict] = []
        self._write()

    def elapsed(self) -> float:
        """Seconds since the journey started."""
        return round(time.monotonic() - self._t0, 3)

    @contextmanager
    def stage(self, label: str) -> Iterator[dict]:
        """Time the enclosed block as stage `label`; marks it failed if it raises."""
        index = self.planned.index(label) + 1 if label in self.planned else len(self.stages) + 1
        entry = {"index": index, "label": label, "start_s": self.elapsed(), "end_s": None,
                 "duration_s": None, "status": "running", "detail": None}
        self.stages.append(entry)
        logger.info("[%s] stage %d/%d started: %s (t+%.1fs)",
                    self.name, index, len(self.planned), label, entry["start_s"])
        self._write()
        try:
            yield entry
        except BaseException:
            self._finish(entry, "failed")
            raise
        self._finish(entry, "done")

    def progress(self, detail: str) -> None:
        """Record where the running stage is (e.g. "round 7/20"); logged and saved only when it changes."""
        running = [entry for entry in self.stages if entry["status"] == "running"]
        if running and running[-1]["detail"] != detail:
            running[-1]["detail"] = detail
            logger.info("[%s] %s: %s (t+%.1fs)", self.name, running[-1]["label"], detail, self.elapsed())
            self._write()

    def add_completed(self, label: str, start_s: float, duration_s: float, detail: str | None = None) -> None:
        """Record a stage timed elsewhere (e.g. inside a subprocess), offset into this journey."""
        self.stages.append({"index": len(self.stages) + 1, "label": label, "start_s": round(start_s, 3),
                            "end_s": round(start_s + duration_s, 3), "duration_s": round(duration_s, 3),
                            "status": "done", "detail": detail})
        self._write()

    def to_dict(self) -> dict:
        running = [entry["label"] for entry in self.stages if entry["status"] == "running"]
        return {
            "name": self.name,
            "started_at": self.started_at,
            "elapsed_s": self.elapsed(),
            "planned_stages": self.planned,
            "current_stage": running[-1] if running else None,
            "stages": self.stages,
        }

    def _finish(self, entry: dict, status: str) -> None:
        entry["end_s"] = self.elapsed()
        entry["duration_s"] = round(entry["end_s"] - entry["start_s"], 3)
        entry["status"] = status
        logger.info("[%s] stage %d/%d %s: %s in %.1fs",
                    self.name, entry["index"], len(self.planned), status, entry["label"], entry["duration_s"])
        self._write()

    def _write(self) -> None:
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.to_dict(), indent=2))
        tmp.replace(self.path)
