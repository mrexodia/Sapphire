"""Owned native-process exit evidence, never a server-session/offline fence."""
from .development import DevelopmentError


class ObservedWorker:
    def __init__(self, worker, report):
        self.worker, self.report = worker, report
        report.update(scope="owned-native-worker-exit-not-server-session-closure",
                      context_entered=False, context_exit_attempted=False,
                      context_exit_completed=False, process_exit_observed=False)

    def __enter__(self):
        active = self.worker.__enter__()
        self.report["context_entered"] = True
        return active

    def __exit__(self, kind, error, traceback):
        self.report["context_exit_attempted"] = True
        try:
            suppressed = self.worker.__exit__(kind, error, traceback)
            self.report["context_exit_completed"] = True
        except BaseException as cleanup_error:
            self.report["context_exit_error_type"] = type(cleanup_error).__name__
            if kind is None:
                raise
            suppressed = False  # Preserve the original failure and record cleanup separately.
        finally:
            # Never retain repr/argv/stderr/exception messages: they can contain
            # credentials. Query the owned Popen handle, not a PID/name search.
            try:
                process = self.worker.process
                pid, code = process.pid, process.poll()
                if type(pid) is int and pid > 0:
                    self.report["process_id"] = pid
                if type(code) is int:
                    self.report.update(process_exit_observed=True, returncode=code)
            except Exception:
                self.report["process_observation_error"] = True
        # Do not mask an earlier gameplay/deadline exception or suppress it.
        # Native Worker.__exit__ normally returns None, but even a test adapter
        # that swallows an exception cannot turn a failed scenario into success.
        if kind is not None:
            return False
        if (suppressed or not self.report["process_exit_observed"]
                or self.report.get("returncode") != 0 or "process_id" not in self.report):
            raise DevelopmentError("native worker exit was not observed as normal")
        return False
