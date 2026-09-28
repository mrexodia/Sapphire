"""Process-specific resource sampling for both Sapphire and the load generator."""
import threading
import time
import psutil


class ProcessMetrics:
    def __init__(self, processes):
        self.processes = {name: psutil.Process(pid) for name, pid in processes.items()}
        self.samples = []
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _sample(self):
        row = {"monotonic": time.monotonic(), "processes": {}}
        for name, process in self.processes.items():
            try:
                cpu = process.cpu_times()
                row["processes"][name] = {"rss_bytes": process.memory_info().rss,
                                            "cpu_seconds": cpu.user + cpu.system}
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                row["processes"][name] = {"unavailable": True}
        self.samples.append(row)
        if len(self.samples) > 7200:
            del self.samples[0]

    def _run(self):
        while not self._stop.wait(1):
            self._sample()

    def start(self):
        self._sample()
        self._thread.start()

    def stop(self):
        self._stop.set()
        self._thread.join(timeout=3)
        self._sample()
