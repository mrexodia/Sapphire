"""Synthetic decline ownership/lifecycle tests; no live gameplay inference."""
import copy
import pytest
from . import run_development
from .support.development import DevelopmentError
from .support import development_decline
from .test_development import profile
from .test_development_party import PartyWorker


class DeclineWorker(PartyWorker):
    def __init__(self, failure=None):
        super().__init__(failure)
        self.wait_budgets = []
        for state in self.states.values():
            state.update(seq=10, between_areas=False)
            for actor in state['actors'].values():
                actor['kind'] = 1
        if failure == 'stale_reply':
            self.states['witness']['party_invite_reply'] = {'answer':0}
        if failure == 'duplicate_peer':
            self.states['mover']['actors']['999'] = copy.deepcopy(self.states['mover']['actors']['2'])

    def request(self, method, bot=None, **args):
        if method == 'capabilities':
            return {'methods': [] if self.party_failure=='old_worker' else sorted(development_decline.METHODS)}
        if method == 'invite_party_bound':
            result = super().request(method, bot, **args)
            for state in self.states.values(): state['seq'] += 1
            if self.party_failure == 'no_invite': self.states['witness']['pending_party_invite'] = None
            if self.party_failure == 'no_invite_result': self.states['mover']['party_invite_result'] = None
            return result
        if method != 'decline_party_bound': return super().request(method, bot, **args)
        state = self.states[bot]
        if self.party_failure == 'raced_invite': state['pending_party_invite']['character_id'] = 999
        if args['expected_party'] != state['party'] or args['expected_invite'] != state['pending_party_invite']:
            raise DevelopmentError('native context changed')
        self.published.append(method)
        state['pending_party_invite'] = None
        state['party_invite_reply'] = {'result':0, 'auth_type':1, 'answer':0, 'name':'Bot Mover'}
        self.states['mover']['party_invite_update'] = {'character_id':102, 'auth_type':1, 'result':5, 'name':'Bot Witness'}
        for value in self.states.values(): value['seq'] += 1
        f = self.party_failure
        if f == 'no_reply': state['party_invite_reply'] = None
        if f == 'no_rejection': self.states['mover']['party_invite_update'] = None
        if f == 'wrong_reply': state['party_invite_reply']['answer'] = 1
        if f == 'wrong_rejection': self.states['mover']['party_invite_update']['character_id'] = 999
        if f == 'new_foreign_invite': state['pending_party_invite'] = {'character_id':999}
        if f == 'membership_appeared': state['party']['id'] = 999
        if f == 'identity_changed': state['characters'][0]['character_id'] = 999
        if f == 'gm_changed': state['gm_rank'] = 90
        if f == 'stale_sequence': state['seq'] = 10
        return {}

    def wait_state(self, bot, predicate, description, timeout=30):
        if 'decline' in description or 'inviter' in description or 'publication result' in description:
            self.wait_budgets.append(timeout)
        return super().wait_state(bot,predicate,description,timeout)


def execute(profile, tmp_path, failure=None, **kwargs):
    worker=DeclineWorker(failure);logins=[]
    def login(*args):
        logins.append(True)
        return {'lobbyHost':'127.0.0.1','lobbyPort':54994,'sId':'private'}
    result=run_development.run(profile,tmp_path/'run',confirmed=True,verify_decline=True,
        worker_factory=lambda *_:worker,login=login,lease_root=tmp_path/'leases',**kwargs)
    return result,worker,logins


def test_exact_decline_requires_both_received_endpoints_and_empty_parties(profile,tmp_path):
    result,worker,_=execute(profile,tmp_path)
    assert result['status']=='passed' and result['worker_closed'] and not result['lease_retained']
    proof=result['decline_verification']
    assert proof['verified'] and proof['both_empty_after_decline']
    # The normal reciprocal Say advances each synthetic session before the decline baseline.
    assert proof['baseline_sequences']==[11,11] and proof['received_sequences']==[13,13]
    assert worker.published==['invite_party_bound','decline_party_bound']
    assert all(0<x<=10 for x in worker.wait_budgets)


@pytest.mark.parametrize('failure', ['old_worker','existing_party','existing_invite','existing_outgoing_invite',
    'stale_reply','duplicate_peer','foreign_invite','raced_invite','invite_rejected','no_invite','no_invite_result',
    'no_reply','no_rejection','wrong_reply','wrong_rejection','new_foreign_invite','membership_appeared',
    'identity_changed','gm_changed','stale_sequence'])
def test_no_retry_or_foreign_cleanup_after_uncertainty(profile,tmp_path,failure):
    result,worker,logins=execute(profile,tmp_path,failure)
    assert result['status']=='failed' and worker.closed and result['lease_retained']
    assert result['decline_verification']=={'requested':True,'verified':False}
    assert len(list((tmp_path/'leases').glob('*.lock')))==2
    assert worker.published.count('invite_party_bound')<=1
    assert worker.published.count('decline_party_bound')<=1
    assert not set(worker.published)-development_decline.METHODS
    if failure=='old_worker': assert not logins
    if failure in ('foreign_invite','raced_invite','invite_rejected','no_invite','no_invite_result'):
        assert worker.published==['invite_party_bound']


def test_mutually_exclusive_party_and_strict_opt_in(profile,tmp_path):
    for flags in ({'verify_decline':1},{'verify_decline':True,'verify_party':True}):
        with pytest.raises(DevelopmentError):
            run_development.run(profile,tmp_path/'invalid',confirmed=True,**flags)
        assert not (tmp_path/'invalid').exists()


def test_late_delivery_is_not_success(profile,tmp_path,monkeypatch):
    clock=[100.0]
    monkeypatch.setattr(development_decline.time,'monotonic',lambda:clock[0])
    original=DeclineWorker.wait_state
    def late(self,*args,**kwargs):
        state=original(self,*args,**kwargs)
        if args[2]=='recipient received exact decline reply':clock[0]=111
        return state
    monkeypatch.setattr(DeclineWorker,'wait_state',late)
    result,worker,_=execute(profile,tmp_path)
    assert result['status']=='failed' and result['lease_retained']
    assert worker.published==['invite_party_bound','decline_party_bound']
