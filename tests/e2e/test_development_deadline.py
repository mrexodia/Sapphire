"""Synthetic cooperative-budget contracts, not hard-kill or server-lock evidence."""
import json

import pytest

from . import run_development
from .support import development_deadline as budgets
from .support.development import DevelopmentError
from .test_development import FakeWorker, profile


class TimedWorker(FakeWorker):
    def __init__(self, now, stage=None, scale=1):
        super().__init__()
        self.now, self.stage, self.deadline_scale = now, stage, scale
        self.timeouts = []

    def request(self, method, bot=None, timeout=10, **args):
        self.timeouts.append((method, timeout))
        result = super().request(method, bot, **args)
        if self.stage == 'request' and method == 'say': self.now[0] = 2
        return result

    def snapshot(self, bot):
        result = super().snapshot(bot)
        if self.stage == 'snapshot': self.now[0] = 2
        return result

    def wait_state(self, bot, predicate, description, timeout=30):
        self.timeouts.append((description, timeout))
        if self.stage == 'wait': self.now[0] = 2
        result = super().wait_state(bot, predicate, description, timeout)
        if self.stage == 'wait_result': self.now[0] = 2
        return result

    def __exit__(self, *args):
        result = super().__exit__(*args)
        if self.stage == 'worker_cleanup': self.now[0] = 2
        return result


def test_delegate_budgets_apply_scale_and_preserve_arguments():
    now = [100.0]
    d = budgets.RunDeadline(6, clock=lambda: now[0])
    raw = TimedWorker(now, scale=3); worker = budgets.DeadlineWorker(raw, d)
    worker.request('say', 'mover', message='one')
    assert raw.timeouts[-1] == ('say', 2)
    assert raw.states['witness']['chat'] == [{'actor': 1, 'message': 'one'}]
    worker.wait_state('mover', lambda s: s['phase'] == 'ready', 'ready', timeout=1)
    assert raw.timeouts[-1] == ('ready', 1)
    now[0] = 106
    with pytest.raises(DevelopmentError): worker.request('say', 'mover', message='never sent')
    assert raw.commands == ['say']


@pytest.mark.parametrize('stage', ['request', 'snapshot', 'wait', 'wait_result', 'predicate'])
def test_late_result_never_passes(stage):
    now = [0.0]; raw = TimedWorker(now, stage)
    worker = budgets.DeadlineWorker(raw, budgets.RunDeadline(1, clock=lambda: now[0]))
    with pytest.raises(DevelopmentError):
        if stage == 'request': worker.request('say', 'mover', message='one')
        elif stage == 'snapshot': worker.snapshot('mover')
        else:
            def predicate(state):
                if stage == 'predicate': now[0] = 2
                return True
            worker.wait_state('mover', predicate, 'ready')
    assert raw.commands == (['say'] if stage == 'request' else [])


@pytest.mark.parametrize('seconds', [True, 0, -1, 901, 1.5, '10', None])
def test_invalid_budget(seconds):
    with pytest.raises(DevelopmentError): budgets.RunDeadline(seconds)


@pytest.mark.parametrize('scale', [True, 0, 4, 1.5])
def test_invalid_delegate_scale(scale):
    with pytest.raises(DevelopmentError):
        budgets.DeadlineWorker(TimedWorker([0.0], scale=scale), budgets.RunDeadline(1))


@pytest.mark.parametrize('timeout', [True, 0, -1, float('nan'), float('inf'), '1'])
def test_invalid_timeout_cannot_publish(timeout):
    raw = TimedWorker([0.0]); worker = budgets.DeadlineWorker(raw, budgets.RunDeadline(1))
    with pytest.raises(DevelopmentError): worker.request('say', 'mover', timeout=timeout, message='never sent')
    assert raw.commands == []


def test_completion_freezes_session_budget_not_cleanup_or_overall_success():
    now = [0.0]; d = budgets.RunDeadline(1, clock=lambda: now[0])
    d.complete(); now[0] = 10
    assert not d.report()['expired'] and d.report()['session_work_completed_within_budget']
    assert d.report()['cleanup_may_exceed_deadline']
    with pytest.raises(DevelopmentError): d.call(lambda: None)  # Completion never authorizes more late work.
    assert 'status' not in d.report()


@pytest.mark.parametrize('stage', ['login', 'factory', 'request', 'wait', 'wait_result', 'worker_cleanup'])
def test_runner_expiry_retains_leases_and_closes_owned_worker(profile, tmp_path, monkeypatch, stage):
    now = [0.0]; monkeypatch.setattr(budgets.time, 'monotonic', lambda: now[0])
    raw = TimedWorker(now, stage); logins = []
    def login(*args):
        logins.append(True)
        if stage == 'login': now[0] = 2
        return {'lobbyHost': '127.0.0.1', 'lobbyPort': 54994, 'sId': 'private'}
    def factory(*args):
        if stage == 'factory': now[0] = 2
        return raw
    report = run_development.run(profile, tmp_path / 'run', confirmed=True, max_seconds=1,
        worker_factory=factory, login=login, lease_root=tmp_path / 'leases')
    assert report['status'] == 'failed' and raw.closed and report['lease_retained']
    assert report['run_deadline']['expired'] and not report['run_deadline']['session_work_completed_within_budget']
    assert len(list((tmp_path / 'leases').glob('*.lock'))) == 2
    if stage in {'login', 'factory'}:
        assert raw.commands == []
        assert len(logins) == (1 if stage == 'login' else 0)
    if stage == 'request': assert raw.commands.count('say') == 1
    assert 'private' not in json.dumps(report)


def test_success_and_programmatic_disabled_default(profile, tmp_path, monkeypatch):
    now = [0.0]; monkeypatch.setattr(budgets.time, 'monotonic', lambda: now[0])
    for maximum, path in ((1, 'bounded'), (None, 'legacy')):
        raw = TimedWorker(now)
        report = run_development.run(profile, tmp_path / path, confirmed=True, max_seconds=maximum,
            worker_factory=lambda *_: raw,
            login=lambda *_: {'lobbyHost': '127.0.0.1', 'lobbyPort': 54994, 'sId': 'private'},
            lease_root=tmp_path / 'leases')
        assert report['status'] == 'passed' and not report['lease_retained'] and raw.closed
        assert report['run_deadline']['enabled'] == (maximum is not None)
        if maximum is not None:
            assert report['run_deadline']['session_work_completed_within_budget']
            assert all(0 < timeout <= 1 for _, timeout in raw.timeouts)
    for maximum in (True, 0, 901):
        with pytest.raises(DevelopmentError):
            run_development.run(profile, tmp_path / 'invalid', confirmed=True, max_seconds=maximum)
    assert not (tmp_path / 'invalid').exists()


@pytest.mark.parametrize('arguments,expected', [([], 300), (['--max-seconds', '2'], 2)])
def test_cli_default_and_explicit_budget(profile, tmp_path, monkeypatch, arguments, expected):
    private = tmp_path / 'profile.json'; private.write_text(json.dumps(profile))
    received = []
    def run(*args, **kwargs):
        assert kwargs['confirmed'] is True
        received.append(kwargs['max_seconds'])
        return {'status': 'passed', 'scope': 'synthetic', 'elapsed_seconds': 0}
    monkeypatch.setattr(run_development, 'run', run)
    assert run_development.main(['--profile', str(private), '--artifacts', str(tmp_path / 'unused'),
                                 '--allow-shared-development', *arguments]) == 0
    assert received == [expected]
