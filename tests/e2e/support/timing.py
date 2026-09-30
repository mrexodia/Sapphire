"""Opt-in pytest phase durations; diagnostic evidence, never a pass/fail gate."""
import json
from pathlib import Path
import time


class PhaseTiming:
    def __init__(self, path):
        self.path = Path(path)
        self.started = time.monotonic()
        self.rows = []

    def pytest_runtest_logreport(self, report):
        self.rows.append({"test": report.nodeid, "phase": report.when,
                          "outcome": report.outcome, "seconds": report.duration})

    def pytest_sessionfinish(self, session, exitstatus):
        totals = {phase: sum(row["seconds"] for row in self.rows if row["phase"] == phase)
                  for phase in ("setup", "call", "teardown")}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Reserve a new report: do not overwrite previous timing evidence.
        with self.path.open("x", encoding="utf-8") as stream:
            json.dump({"version": 1, "scope": "pytest-phase-timing-not-coverage",
                       "elapsed_seconds": time.monotonic() - self.started,
                       "pytest_exit_code": int(exitstatus), "phase_seconds": totals,
                       "reports": self.rows,
                       "note": "call includes in-scenario restarts; phase totals do not isolate gameplay CPU time"},
                      stream, indent=2)
