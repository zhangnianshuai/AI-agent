"""Lightweight Agent observability.

Trace records intentionally store operational metadata rather than full prompts or
candidate answers. This makes the traces useful for latency/tool debugging without
turning the log file into a second copy of sensitive interview content.
"""

from __future__ import annotations

import json
from collections import deque
import threading
import time
import uuid
from pathlib import Path
from typing import Any

_TRACE_DIR = Path(__file__).resolve().parent.parent.parent / "logs"
_TRACE_FILE = _TRACE_DIR / "agent_trace.jsonl"
_WRITE_LOCK = threading.Lock()
_MAX_EVENT_VALUE = 500


def _safe_value(value: Any):
    if isinstance(value, (str, int, float, bool)) or value is None:
        if isinstance(value, str) and len(value) > _MAX_EVENT_VALUE:
            return value[:_MAX_EVENT_VALUE] + "..."
        return value
    if isinstance(value, (list, tuple)):
        return [_safe_value(v) for v in value[:20]]
    if isinstance(value, dict):
        return {str(k): _safe_value(v) for k, v in list(value.items())[:30]}
    return str(value)[:_MAX_EVENT_VALUE]


class AgentTrace:
    """One request/span trace persisted as a single JSONL record."""

    def __init__(self, component: str, **metadata):
        self.trace_id = uuid.uuid4().hex
        self.component = component
        self.started_at = time.time()
        self._started_mono = time.perf_counter()
        self.metadata = {k: _safe_value(v) for k, v in metadata.items()}
        self.events: list[dict] = []
        self._finished = False

    def event(self, event_type: str, **fields):
        if self._finished:
            return
        self.events.append(
            {
                "type": event_type,
                "at_ms": round((time.perf_counter() - self._started_mono) * 1000, 2),
                **{k: _safe_value(v) for k, v in fields.items()},
            }
        )

    def finish(self, status: str = "ok", error: str | None = None, **fields):
        if self._finished:
            return
        self._finished = True
        record = {
            "trace_id": self.trace_id,
            "component": self.component,
            "started_at": self.started_at,
            "duration_ms": round((time.perf_counter() - self._started_mono) * 1000, 2),
            "status": status,
            "metadata": self.metadata,
            "events": self.events,
            **{k: _safe_value(v) for k, v in fields.items()},
        }
        if error:
            record["error"] = _safe_value(error)
        _append_record(record)


def _append_record(record: dict):
    _TRACE_DIR.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
    with _WRITE_LOCK:
        with _TRACE_FILE.open("a", encoding="utf-8") as fp:
            fp.write(line + "\n")


def read_recent_traces(limit: int = 100) -> list[dict]:
    """Read the most recent trace records for the admin diagnostics API."""
    limit = max(1, min(int(limit), 500))
    if not _TRACE_FILE.exists():
        return []

    # Read only the tail records instead of loading the whole trace file into memory.
    with _WRITE_LOCK:
        with _TRACE_FILE.open("r", encoding="utf-8", errors="replace") as fp:
            lines = deque(fp, maxlen=limit)

    result = []
    for line in lines:
        try:
            result.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return result
