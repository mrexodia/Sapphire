"""Diagnostic wall time for the manual client lane, not gameplay/CPU coverage."""
from __future__ import annotations

import time


class ClientPhaseTiming:
    def __init__(self, *, clock=time.monotonic):
        self.clock = clock
        self.started = self.phase_started = clock()
        self.phase = "setup"
        self.rows = []
        self.finished = None

    def _record(self, now):
        self.rows.append({"phase": self.phase,
                          "seconds": now - self.phase_started})

    def transition(self, phase):
        if self.finished is not None:
            raise RuntimeError("manual phase timing already finished")
        now = self.clock()
        self._record(now)
        self.phase, self.phase_started = phase, now

    def finish(self):
        if self.finished is None:
            self.finished = self.clock()
            self._record(self.finished)
        return {"version": 1, "scope": "manual-client-phase-wall-time-not-coverage",
                "elapsed_seconds": self.finished - self.started,
                "phases": [dict(row) for row in self.rows],
                "note": "Includes operator waits and worker unwinding; cleanup is client/environment teardown. Not gameplay CPU time."}
