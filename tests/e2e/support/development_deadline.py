"""Cooperative whole-run success budget; not preemption or server exclusion."""
import math
import time

from .development import DevelopmentError


class RunDeadline:
    def __init__(self, seconds, *, started=None, clock=None):
        if type(seconds) is not int or not 1 <= seconds <= 900:
            raise DevelopmentError("max_seconds must be an integer in 1..900")
        self.clock = clock or time.monotonic
        self.started = self.clock() if started is None else started
        self.seconds = seconds
        self.deadline = self.started + seconds
        self.completed_at = None

    def check(self):
        remaining = self.deadline - self.clock()
        if remaining <= 0:
            raise DevelopmentError("shared-development run deadline expired; no retry")
        return remaining

    def call(self, function, *args, **kwargs):
        self.check()
        result = function(*args, **kwargs)
        self.check()  # A response arriving late is not a successful step.
        return result

    def complete(self):
        finished = self.clock()
        if finished >= self.deadline:
            raise DevelopmentError("shared-development run deadline expired; no retry")
        self.completed_at = finished

    def report(self):
        return {"enabled": True, "limit_seconds": self.seconds,
                "expired": self.completed_at is None and self.clock() >= self.deadline,
                "session_work_completed_within_budget": self.completed_at is not None,
                "scope": "cooperative-success-deadline-not-hard-process-limit",
                "cleanup_may_exceed_deadline": True}


class DeadlineWorker:
    """Bound new RPCs/waits; never take ownership of the underlying worker.

    A delegate wait may already be in a snapshot RPC with its ordinary timeout;
    an HTTP call/worker startup may likewise be in flight. Reject their late
    results, but leave context-manager cleanup to the original owner.
    """
    def __init__(self, worker, deadline):
        self.worker, self.deadline = worker, deadline
        scale = getattr(worker, "deadline_scale", 1)
        if type(scale) is not int or not 1 <= scale <= 3:
            raise DevelopmentError("unsupported worker deadline scale")
        self.deadline_scale = scale

    def budget(self, timeout):
        if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0:
            raise DevelopmentError("worker timeout must be finite and positive")
        return min(timeout, self.deadline.check() / self.deadline_scale)

    def request(self, method, bot=None, timeout=10, **args):
        return self.deadline.call(self.worker.request, method, bot,
                                  timeout=self.budget(timeout), **args)

    def snapshot(self, bot):
        return self.deadline.call(self.worker.snapshot, bot)

    def wait_state(self, bot, predicate, description, timeout=30):
        def guarded(state):
            return self.deadline.call(predicate, state)
        return self.deadline.call(self.worker.wait_state, bot, guarded, description,
                                  timeout=self.budget(timeout))
