"""Visible Tell policy/synthetic delivery tests, not live messaging evidence."""
import copy

import pytest

from . import run_development
from .support.development import DevelopmentError
from .support import development_tell
from .test_development import profile
from .test_development_party import PartyWorker


class TellWorker(PartyWorker):
    def __init__(self, failure=None):
        super().__init__()
        self.tell_failure, self.tells_sent, self.altered = failure, [], False
        for state in self.states.values():
            state.update(seq=100, tells=[], between_areas=False)
            for actor in state['actors'].values(): actor['kind'] = 1
        self.original = copy.deepcopy(self.states['mover'])

    def snapshot(self, bot):
        if not self.altered:
            self.altered = True
            state = self.states['mover']
            if self.tell_failure == 'changed_identity': state['characters'][0]['character_id'] = 999
            if self.tell_failure == 'duplicate_peer': state['actors']['99'] = copy.deepcopy(state['actors']['2'])
            if self.tell_failure == 'npc_peer': state['actors']['2']['kind'] = 3
            if self.tell_failure == 'transition': state['between_areas'] = True
            if self.tell_failure == 'existing_party': state['party']['id'] = 77
            if self.tell_failure == 'existing_invite': state['pending_party_invite'] = {'character_id':999}
            if self.tell_failure == 'missing_sequence': state.pop('seq')
        return super().snapshot(bot)

    def wait_state(self, bot, predicate, description, timeout=30):
        result = super().wait_state(bot, predicate, description, timeout)
        if self.tell_failure == 'late_receive' and description == 'fresh exact dedicated-peer Tell':
            self.clock[0] += 11
        return result

    def request(self, method, bot=None, **args):
        if method == 'capabilities':
            result = super().request(method, bot, **args)
            if self.tell_failure != 'old_worker': result['methods'].append('tell_visible')
            return result
        if method != 'tell_visible': return super().request(method, bot, **args)
        self.tells_sent.append((bot, args))
        other = 'witness' if bot == 'mover' else 'mover'
        sender, receiver = self.states[bot], self.states[other]
        peer = receiver['characters'][0]
        assert args['target'] == peer['entity_id'] and args['name'] == peer['name']
        identity = sender['characters'][0]
        receiver['seq'] += 1
        row = {'actor':identity['entity_id'], 'character_id':identity['character_id'], 'name':identity['name'],
               'party_id':0, 'message':args['message'], 'token':receiver['seq']}
        if self.tell_failure == 'wrong_sender': row['character_id'] = 999
        if self.tell_failure == 'wrong_actor': row['actor'] = 999
        if self.tell_failure == 'wrong_name': row['name'] = 'Other Player'
        if self.tell_failure == 'wrong_party': row['party_id'] = 9
        if self.tell_failure == 'wrong_message': row['message'] += ' altered'
        if self.tell_failure == 'stale_token': row['token'] -= 1
        if self.tell_failure == 'future_token': row['token'] += 1
        if self.tell_failure == 'boolean_token': row['token'] = True
        if self.tell_failure != 'no_delivery': receiver['tells'].append(row)
        if self.tell_failure == 'duplicate_delivery': receiver['tells'].append(copy.deepcopy(row))
        if self.tell_failure == 'late': self.clock[0] += 11
        return {}  # Empty successful publication is not delivery evidence.


def execute(profile, tmp_path, failure=None, enabled=True, party=False, reconnect=False):
    fake, logins = TellWorker(failure), []
    def login(*args):
        logins.append(1)
        return {'lobbyHost':'127.0.0.1', 'lobbyPort':54994, 'sId':'private'}
    result = run_development.run(profile, tmp_path / 'run', confirmed=True, verify_tell=enabled,
        verify_party=party, verify_reconnect=reconnect, worker_factory=lambda *_:fake,
        login=login, lease_root=tmp_path / 'leases')
    return result, fake, logins


def test_visible_tell_both_fresh_deliveries(profile, tmp_path):
    report, fake, _ = execute(profile, tmp_path)
    assert report['status'] == 'passed' and not report['lease_retained'] and fake.closed
    assert [name for name,args in fake.tells_sent] == ['mover','witness']
    proof = report['tell_verification']
    assert proof['verified'] and len(proof['received_tells']) == 2
    for row in proof['received_tells']:
        assert row['baseline_seq'] < row['received']['token'] <= row['received_seq']
        assert row['received']['character_id'] == row['sender']['character_id']


@pytest.mark.parametrize('failure', ['old_worker','changed_identity','duplicate_peer','npc_peer','transition',
    'existing_party','existing_invite','missing_sequence','wrong_sender','wrong_actor','wrong_name',
    'wrong_party','wrong_message','stale_token','future_token','boolean_token','no_delivery','duplicate_delivery'])
def test_failed_tell_never_retries_or_claims_delivery(profile, tmp_path, failure):
    report, fake, logins = execute(profile, tmp_path, failure)
    assert report['status'] == 'failed' and report['lease_retained'] and fake.closed
    assert report['tell_verification'] == {'requested':True,'verified':False}
    assert len(fake.tells_sent) <= 1
    if failure == 'old_worker': assert not logins
    assert len(list((tmp_path / 'leases').glob('*.lock'))) == 2


def test_disabled_tell_and_invalid_flag(profile, tmp_path):
    report, fake, _ = execute(profile, tmp_path, enabled=False)
    assert report['status'] == 'passed' and not fake.tells_sent
    with pytest.raises(DevelopmentError):
        run_development.run(profile, tmp_path / 'invalid', confirmed=True, verify_tell=1)
    assert not (tmp_path / 'invalid').exists()


def test_tell_after_disband_before_reconnect(profile, tmp_path):
    report, fake, _ = execute(profile, tmp_path, party=True, reconnect=True)
    assert report['status'] == 'passed'
    phases = [row['phase'] for row in report['timings']]
    assert phases.index('party_owned_disband_and_empty_state') < phases.index('tell_visible_bidirectional')
    assert phases.index('tell_visible_bidirectional') < phases.index('reconnect_fresh_http_login')


@pytest.mark.parametrize('failure', ['late', 'late_receive'])
def test_late_success_is_not_retried(profile, tmp_path, monkeypatch, failure):
    clock = [0.0]
    monkeypatch.setattr(development_tell.time, 'monotonic', lambda:clock[0])
    fake = TellWorker(failure); fake.clock = clock
    report = run_development.run(profile, tmp_path / 'run', confirmed=True, verify_tell=True,
        worker_factory=lambda *_:fake, login=lambda *_:{'lobbyHost':'127.0.0.1','lobbyPort':54994,'sId':'private'},
        lease_root=tmp_path / 'leases')
    assert report['status'] == 'failed' and len(fake.tells_sent) == 1
