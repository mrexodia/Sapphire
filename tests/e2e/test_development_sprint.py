"""Synthetic Sprint policy/delivery contracts, not live gameplay evidence."""
import copy

import pytest

from . import run_development
from .support import development_sprint as sprint
from .support.development import DevelopmentError
from .test_development import profile
from .test_development_party import PartyWorker


class SprintWorker(PartyWorker):
    def __init__(self, failure=None):
        super().__init__()
        self.failure, self.casts, self.altered = failure, [], False
        for state in self.states.values():
            own = state['characters'][0]
            state['actors'][str(own['entity_id'])] = {'name': own['name'], 'gm_rank': 0, 'position': [0, 0, 0]}
            state.update(seq=100, between_areas=False, combat={
                'starting_action_guard_remaining_ms': 0, 'effects': [], 'starts': [],
                'hud_params': [{'target': 1, 'tp': 0}]})
            for actor in state['actors'].values():
                actor.update(kind=1, hp=100, tp=1000)
        self.original = copy.deepcopy(self.states['mover'])

    def snapshot(self, bot):
        if not self.altered:
            self.altered = True
            s = self.states['mover']
            if self.failure == 'changed_identity': s['characters'][0]['character_id'] = 999
            if self.failure == 'duplicate_peer': s['actors']['99'] = copy.deepcopy(s['actors']['2'])
            if self.failure == 'npc_peer': s['actors']['2']['kind'] = 3
            if self.failure == 'gm_peer': s['actors']['2']['gm_rank'] = 1
            if self.failure == 'transition': s['between_areas'] = True
            if self.failure == 'party': s['party']['id'] = 99
            if self.failure == 'invite': s['pending_party_invite'] = {'character_id': 999}
            if self.failure == 'missing_sequence': s.pop('seq')
            if self.failure == 'no_tp': s['actors']['1']['tp'] = 0
            if self.failure == 'pacing': s['combat']['starting_action_guard_remaining_ms'] = 2500
            if self.failure == 'old_history': s['combat']['starts'].append({'source': 1, 'action': 3})
            if self.failure == 'full_history': s['combat']['hud_params'] *= 128
            if self.failure == 'malformed_history': s['combat']['effects'] = {}
        return super().snapshot(bot)

    def wait_state(self, bot, predicate, description, timeout=30):
        result = super().wait_state(bot, predicate, description, timeout)
        if ((self.failure == 'late_receive' and description == 'fresh exact Sprint effect and zero TP')
                or (self.failure == 'late_readiness' and description == 'natural Sprint TP/pacing readiness')):
            self.clock[0] += 11
        return result

    def request(self, method, bot=None, **args):
        if method == 'capabilities':
            return {'methods': [] if self.failure == 'old_worker' else ['sprint']}
        if method != 'sprint':
            return super().request(method, bot, **args)
        assert bot == 'mover' and args == {}
        self.casts.append(bot)
        effect = {'source': 1, 'target': 1, 'action': 3, 'kind': 1, 'request': 7, 'result': 8,
                  'effects': [{'type': 18, 'value': 50, 'flag': 128, 'args': [0, 0, 30]}],
                  'source_effects': []}
        for name, state in self.states.items():
            state['seq'] += 10
            c = state['combat']
            if self.failure != 'no_effect': c['effects'].append(copy.deepcopy(effect))
            if self.failure != 'stale_zero': c['hud_params'].append({'target': 1, 'tp': 0})
            if name == 'mover' and self.failure != 'no_start':
                c['starts'].append({'source': 1, 'action': 3, 'group': 56, 'recast_centiseconds': 3000})
        c = self.states['witness']['combat']
        if self.failure == 'wrong_source': c['effects'][0]['source'] = 2
        if self.failure == 'wrong_target': c['effects'][0]['target'] = 2
        if self.failure == 'wrong_request': c['effects'][0]['request'] = 8
        if self.failure == 'wrong_action': c['effects'][0]['action'] = 99
        if self.failure == 'boolean_identity': c['effects'][0]['source'] = True
        if self.failure == 'wrong_effect': c['effects'][0]['effects'][0]['value'] = 99
        if self.failure == 'boolean_effect': c['effects'][0]['effects'][0]['args'][0] = False
        if self.failure == 'different_result': c['effects'][0]['result'] = 99
        if self.failure == 'duplicate_effect': c['effects'] *= 2
        if self.failure == 'wrong_hud_target': c['hud_params'][-1]['target'] = 2
        if self.failure == 'boolean_tp': c['hud_params'][-1]['tp'] = False
        if self.failure == 'rollover': c['hud_params'][0]['tp'] = 99
        if self.failure == 'saturated_after': c['hud_params'] *= 64
        if self.failure == 'stale_sequence': self.states['witness']['seq'] = 100
        if self.failure == 'changed_after': self.states['witness']['characters'][0]['character_id'] = 999
        if self.failure == 'wrong_start': self.states['mover']['combat']['starts'][0]['group'] = 99
        if self.failure == 'duplicate_start': self.states['mover']['combat']['starts'] *= 2
        if self.failure == 'late': self.clock[0] += 11
        return {'request': True if self.failure == 'invalid_request' else 7}


def execute(profile, tmp_path, failure=None, enabled=True):
    fake, logins = SprintWorker(failure), []
    def login(*args):
        logins.append(1)
        return {'lobbyHost': '127.0.0.1', 'lobbyPort': 54994, 'sId': 'private'}
    report = run_development.run(profile, tmp_path / 'run', confirmed=True, verify_sprint=enabled,
        worker_factory=lambda *_: fake, login=login, lease_root=tmp_path / 'leases')
    return report, fake, logins


def test_one_self_sprint_with_independent_fresh_effect_and_tp(profile, tmp_path):
    report, fake, _ = execute(profile, tmp_path)
    assert report['status'] == 'passed' and not report['lease_retained'] and fake.closed
    assert fake.casts == ['mover']
    proof = report['sprint_verification']
    assert proof['verified'] and proof['request'] == 7 and proof['tp_before'] == 1000
    assert proof['receipts'][0]['effect'] == proof['receipts'][1]['effect']
    assert proof['receipts'][0]['start']['group'] == 56
    assert proof['receipts'][1]['start'] is None
    assert all(r['received_seq'] > b['seq'] for r, b in zip(proof['receipts'], proof['baselines']))
    fake.states['mover']['combat']['hud_params'][0]['tp'] = 99
    assert proof['baselines'][0]['histories']['hud_params'][0]['tp'] == 0


@pytest.mark.parametrize('failure', ['old_worker', 'changed_identity', 'duplicate_peer', 'npc_peer', 'gm_peer',
    'transition', 'party', 'invite', 'missing_sequence', 'no_tp', 'pacing', 'old_history', 'full_history',
    'malformed_history', 'no_effect', 'stale_zero', 'no_start', 'wrong_source', 'wrong_target', 'wrong_request',
    'wrong_action', 'boolean_identity', 'wrong_effect', 'boolean_effect', 'different_result', 'duplicate_effect',
    'wrong_hud_target', 'boolean_tp', 'rollover', 'saturated_after', 'stale_sequence', 'changed_after',
    'wrong_start', 'duplicate_start', 'invalid_request'])
def test_failure_is_not_retried_and_retains_leases(profile, tmp_path, failure):
    report, fake, logins = execute(profile, tmp_path, failure)
    assert report['status'] == 'failed' and report['lease_retained'] and fake.closed
    assert report['sprint_verification'] == {'requested': True, 'verified': False}
    preflight = {'old_worker', 'changed_identity', 'duplicate_peer', 'npc_peer', 'gm_peer',
                 'transition', 'party', 'invite', 'missing_sequence', 'no_tp', 'pacing',
                 'old_history', 'full_history', 'malformed_history'}
    assert fake.casts == ([] if failure in preflight else ['mover'])
    assert report['error_type'] == 'DevelopmentError'
    if failure == 'old_worker': assert not logins
    assert len(list((tmp_path / 'leases').glob('*.lock'))) == 2


def test_default_unchanged_and_strict_opt_in(profile, tmp_path):
    report, fake, _ = execute(profile, tmp_path, enabled=False)
    assert report['status'] == 'passed' and not fake.casts
    assert report['sprint_verification'] == {'requested': False, 'verified': False}
    with pytest.raises(DevelopmentError):
        run_development.run(profile, tmp_path / 'invalid', confirmed=True, verify_sprint=1)
    assert not (tmp_path / 'invalid').exists()


@pytest.mark.parametrize('failure', ['late', 'late_receive', 'late_readiness'])
def test_late_success_cannot_pass(profile, tmp_path, monkeypatch, failure):
    clock = [0.0]
    monkeypatch.setattr(sprint.time, 'monotonic', lambda: clock[0])
    fake = SprintWorker(failure); fake.clock = clock
    report = run_development.run(profile, tmp_path / 'run', confirmed=True, verify_sprint=True,
        worker_factory=lambda *_: fake,
        login=lambda *_: {'lobbyHost': '127.0.0.1', 'lobbyPort': 54994, 'sId': 'private'},
        lease_root=tmp_path / 'leases')
    assert report['status'] == 'failed'
    assert fake.casts == ([] if failure == 'late_readiness' else ['mover'])
