import json
from pathlib import Path
import pytest

from .support.environment import Environment
from .support.worker import Worker
from .support.timing import PhaseTiming


def pytest_addoption(parser):
    parser.addoption("--e2e-worker", help="Path to the headless worker (required for worker contract tests)")
    parser.addoption("--e2e-profile", help="Local disposable-server profile JSON (opts into live E2E)")
    parser.addoption("--e2e-timings", help="Write pytest setup/call/teardown durations to a NEW JSON file")


def pytest_configure(config):
    config.addinivalue_line("markers", "live: requires matching game assets and isolated Sapphire servers")
    path = config.getoption("--e2e-timings")
    if path:
        if Path(path).exists():
            raise pytest.UsageError("--e2e-timings requires a new output path")
        config.pluginmanager.register(PhaseTiming(path), "e2e-phase-timing")


@pytest.fixture
def worker_path(request):
    value = request.config.getoption("--e2e-worker")
    if not value:
        pytest.skip("worker contract tests require explicit --e2e-worker")
    path = Path(value).resolve()
    if not path.is_file():
        pytest.fail(f"worker does not exist: {path}")
    return path


@pytest.fixture
def worker(worker_path, tmp_path):
    with Worker(worker_path, tmp_path / "worker") as instance:
        yield instance


@pytest.fixture
def environment(request):
    profile_path = request.config.getoption("--e2e-profile")
    if not profile_path:
        pytest.skip("live E2E requires explicit --e2e-profile; synthetic tests are not live coverage")
    profile = json.loads(Path(profile_path).read_text(encoding="utf-8"))
    instance = Environment(profile)
    try:
        instance.start()
        yield instance
    finally:
        instance.close()


@pytest.fixture
def live_worker(environment, request):
    name = request.node.name.replace("/", "_")
    with Worker(environment.worker, environment.artifacts / name,
                environment.deadline_scale) as instance:
        yield instance
    environment.check_alive()
