"""Synthetic teardown and failure-report contracts, not server offline proof."""
import json
from types import SimpleNamespace

import pytest

from . import run_development
from .support.development import DevelopmentError
from .support.development_worker_exit import ObservedWorker
from .test_development import FakeWorker, profile


class ExitWorker:
    def __init__(self, code=0, pid=12345, close_error=None, poll_error=False, suppress=False):
        self.code, self.close_error, self.poll_error, self.suppress = code, close_error, poll_error, suppress
        self.exit_calls = 0
        self.process = SimpleNamespace(pid=pid, poll=self.poll)

    def poll(self):
        if self.poll_error:
            raise RuntimeError('private diagnostic must not be copied')
        return self.code

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.exit_calls += 1
        if self.close_error: raise self.close_error
        return self.suppress


def test_zero_exit_is_distinct_from_server_logout_evidence():
    worker, report = ExitWorker(), {}
    with ObservedWorker(worker, report) as active:
        assert active is worker
        assert report['context_entered'] and not report['process_exit_observed']
    assert worker.exit_calls == 1
    assert report == {'scope': 'owned-native-worker-exit-not-server-session-closure',
        'context_entered': True, 'context_exit_attempted': True, 'context_exit_completed': True,
        'process_exit_observed': True, 'process_id': 12345, 'returncode': 0}


@pytest.mark.parametrize('options', [{'code': 1}, {'code': -9}, {'code': None}, {'code': True},
    {'code': 'private'}, {'pid': True}, {'pid': 0}, {'pid': 'private'}, {'poll_error': True}, {'suppress': True}])
def test_abnormal_unknown_or_unbound_exit_cannot_pass(options):
    worker, report = ExitWorker(**options), {}
    with pytest.raises(DevelopmentError):
        with ObservedWorker(worker, report): pass
    assert worker.exit_calls == 1 and report['context_exit_completed']
    assert 'private' not in json.dumps(report)


@pytest.mark.parametrize('code', [0, 1, None])
@pytest.mark.parametrize('cleanup_failure', [False, True])
def test_original_failure_survives_teardown_and_suppression(code, cleanup_failure):
    worker = ExitWorker(code=code, close_error=OSError('private cleanup') if cleanup_failure else None, suppress=True)
    report = {}
    with pytest.raises(ValueError, match='original scenario'):
        with ObservedWorker(worker, report): raise ValueError('original scenario')
    assert worker.exit_calls == 1 and report['context_exit_attempted']
    assert report['context_exit_completed'] is (not cleanup_failure)
    if cleanup_failure: assert report['context_exit_error_type'] == 'OSError'
    assert 'private' not in json.dumps(report) and 'original scenario' not in json.dumps(report)


def test_cleanup_failure_alone_propagates_and_exit_is_still_observed():
    report = {}
    with pytest.raises(OSError):
        with ObservedWorker(ExitWorker(close_error=OSError('private')), report): pass
    assert report['process_exit_observed'] and report['returncode'] == 0
    assert not report['context_exit_completed'] and report['context_exit_error_type'] == 'OSError'
    assert 'private' not in json.dumps(report)


@pytest.mark.parametrize('scenario_failure,code', [(False, 0), (False, 1), (False, None), (True, 0), (True, 1)])
def test_runner_releases_leases_only_after_normal_observed_exit(profile, tmp_path, scenario_failure, code):
    raw = FakeWorker(); raw.process = SimpleNamespace(pid=12345, poll=lambda: code)
    original_request = raw.request
    def request(method, *args, **kwargs):
        if scenario_failure and method == 'say': raise ValueError('private scenario')
        return original_request(method, *args, **kwargs)
    raw.request = request
    report = run_development.run(profile, tmp_path / 'run', confirmed=True,
        worker_factory=lambda *_: raw,
        login=lambda *_: {'lobbyHost':'127.0.0.1', 'lobbyPort':54994, 'sId':'private'},
        lease_root=tmp_path / 'leases')
    success = not scenario_failure and code == 0
    assert report['status'] == ('passed' if success else 'failed') and raw.closed
    assert report['lease_retained'] is (not success)
    assert report['worker_exit']['context_exit_completed']
    assert report['worker_exit']['process_exit_observed'] is (code is not None)
    assert report['worker_closed'] is success  # Legacy normal-path flag, not independent offline proof.
    if scenario_failure: assert report['error_type'] == 'ValueError'
    assert len(list((tmp_path / 'leases').glob('*.lock'))) == (0 if success else 2)
    assert 'private' not in json.dumps(report)


def test_constructor_failure_stays_unknown_not_reported_as_an_exit(profile, tmp_path):
    def factory(*args): raise RuntimeError('private constructor failure')
    report = run_development.run(profile, tmp_path / 'run', confirmed=True,
        worker_factory=factory, lease_root=tmp_path / 'leases')
    assert report['status'] == 'failed' and report['lease_retained']
    assert report['worker_exit'] == {'context_entered':False,'context_exit_attempted':False,
                                    'context_exit_completed':False,'process_exit_observed':False}
    assert 'private' not in json.dumps(report)
