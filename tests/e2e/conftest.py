import pytest

from .support.devserver import DevServer, load_profile
from .support.worker import Worker


def pytest_addoption(parser):
    parser.addoption("--e2e-worker", help="Path to the headless worker (worker contract tests only)")
    parser.addoption("--e2e-profile", help="Profile JSON pointing at the running dev stack (enables live tests)")
    parser.addoption("--e2e-keep-bots", action="store_true",
                     help="Do not purge bot_ accounts before or after the session (keeps bots and any bot_ test account you are using in game)")


def pytest_configure(config):
    config.addinivalue_line("markers", "live: needs a running local Sapphire stack with BotApi enabled")


@pytest.fixture
def worker_path(request):
    value = request.config.getoption("--e2e-worker")
    if not value:
        pytest.skip("worker contract tests require --e2e-worker")
    from pathlib import Path
    path = Path(value).resolve()
    if not path.is_file():
        pytest.fail(f"worker does not exist: {path}")
    return path


@pytest.fixture
def worker(worker_path, tmp_path):
    with Worker(worker_path, tmp_path / "worker") as instance:
        yield instance


@pytest.fixture(scope="session")
def dev_server(request):
    profile_path = request.config.getoption("--e2e-profile")
    if not profile_path:
        pytest.skip("live tests require --e2e-profile")
    server = DevServer(load_profile(profile_path))
    server.check_alive()
    keep = request.config.getoption("--e2e-keep-bots")
    if not keep:
        server.purge_bots()
    yield server
    if not keep:
        server.purge_bots()


@pytest.fixture
def server(dev_server):
    return dev_server


@pytest.fixture
def live_worker(server, request):
    name = request.node.name.replace("/", "_").replace("[", "-").replace("]", "")
    with Worker(server.worker, server.artifacts / name, server.deadline_scale) as instance:
        yield instance
