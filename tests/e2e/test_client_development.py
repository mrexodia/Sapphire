"""Graphical/development bridge contracts, not client execution evidence."""
import copy
from types import SimpleNamespace

import pytest

from .support import client_development as bridge
from .support.development import DevelopmentError
from .support.worker import Worker, WorkerError


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    worker=tmp_path/'worker'; worker.write_bytes(b'fixture')
    env=SimpleNamespace(worker=worker,api_port=5000,lobby_port=54994)
    rows=[{'username':f'e2e_{name}','password':'private-'+name,'name':f'Tester {name}'} for name in ('First','Second','Viewer')]
    monkeypatch.setattr(bridge,'movement_route',lambda p:([[0,0,0],[1,0,0]],'a'*64))
    return env,rows


def test_only_bot_credentials_enter_runner_profile(fixture):
    env,rows=fixture
    profile=bridge.development_profile(env,*rows,'catalog.json')
    assert [r['username'] for r in profile['accounts']]==[r['username'] for r in rows[:2]]
    assert rows[2]['password'] not in str(profile) and rows[2]['name'] not in str(profile)


@pytest.mark.parametrize('key',['username','name'])
@pytest.mark.parametrize('index',[0,1])
def test_viewer_cannot_be_either_bot(fixture,key,index):
    env,rows=fixture
    rows[index][key]=rows[2][key]
    with pytest.raises(DevelopmentError): bridge.development_profile(env,*rows,'catalog.json')


def completed():
    identity={'name':'Tester Viewer','entity_id':3,'gm_rank':0}
    return {'status':'passed','scope':'shared-development-not-acceptance','lease_retained':False,
            'worker_closed':True,
            'worker_exit':{'scope':'owned-native-worker-exit-not-server-session-closure',
                           'context_entered':True,'context_exit_attempted':True,
                           'context_exit_completed':True,'process_exit_observed':True,
                           'process_id':12345,'returncode':0},
            'lease_snapshot':{'version':1,
                'scope':'exact-local-account-lease-snapshot-not-server-session-or-offline-proof',
                'state':'clear','expected_lease_count':2,'present_lease_count':0,
                'records':[{'lease_index':0,'state':'absent'},{'lease_index':1,'state':'absent'}],
                'retained_run_id':None,'profile_or_account_values_disclosed':False,
                'lease_paths_or_keys_disclosed':False,'unrelated_entries_inspected':False,
                'filesystem_mutation_performed':False,'server_or_database_contacted':False,
                'active_session_checked':False,'offline_verified':False,'release_authorized':False,
                'cross_file_snapshot_atomic':False,'retained_receipts_match_run':False},
            'lease_snapshot_matches_run_state':True,
            'administrative_preparation_wait_enabled':False,'database_access':False,
            'world_restart_performed':False,'movement_waypoints_per_cycle':2,
            **{key:{'requested':True,'verified':True} for key in ('party_verification','tell_verification','reconnect_verification')},
            'viewer_verification':{'requested':True,'verified':True,'viewer_login_or_control_performed':False,
                                   'start':{'identity':copy.deepcopy(identity)},'finish':{'identity':copy.deepcopy(identity)}}}


def test_report_requires_all_subchecks_and_same_non_gm_viewer():
    report=completed(); proof=bridge.require_graphical_check(report,'Tester Viewer',3)
    assert proof['status']=='passed' and proof['rendered_bot_actions_verified'] is False
    for key in ('party_verification','tell_verification','reconnect_verification','viewer_verification'):
        wrong=copy.deepcopy(report); wrong[key]['verified']=False
        with pytest.raises(DevelopmentError): bridge.require_graphical_check(wrong,'Tester Viewer',3)
    for stage in ('start','finish'):
        wrong=copy.deepcopy(report); wrong['viewer_verification'][stage]['identity']['entity_id']=999
        with pytest.raises(DevelopmentError): bridge.require_graphical_check(wrong,'Tester Viewer',3)


@pytest.mark.parametrize('field,value',[('status','failed'),('lease_retained',True),('worker_closed',False),
    ('worker_exit',None),('lease_snapshot',None),('lease_snapshot_matches_run_state',False),
    ('administrative_preparation_wait_enabled',True),('database_access',True),
    ('world_restart_performed',True),('movement_waypoints_per_cycle',0)])
def test_partial_or_wrong_scope_is_not_graphical_bridge_success(field,value):
    report=completed(); report[field]=value
    with pytest.raises(DevelopmentError): bridge.require_graphical_check(report,'Tester Viewer',3)


@pytest.mark.parametrize('field,value',[
    ('context_entered',False),('context_exit_attempted',False),
    ('context_exit_completed',False),('process_exit_observed',False),
    ('process_id',0),('process_id',True),('returncode',1),('returncode',True),
    ('scope','server-session-closed')])
def test_graphical_bridge_rejects_malformed_or_failed_worker_exit(field,value):
    report=completed();report['worker_exit'][field]=value
    with pytest.raises(DevelopmentError):
        bridge.require_graphical_check(report,'Tester Viewer',3)


def test_activity_budget_caps_calls_and_rejects_late_success(monkeypatch):
    clock=[10.0]; monkeypatch.setattr(bridge.time,'monotonic',lambda:clock[0])
    worker=object.__new__(bridge.ActivityWorker); worker.activity_deadline=15; worker.deadline_scale=2
    assert worker.budget(30)==2.5
    calls=[]
    def request(self,method,bot=None,timeout=10,**args):
        calls.append(timeout); clock[0]=16
        return {}  # Late acknowledgement cannot make the operation pass.
    monkeypatch.setattr(Worker,'request',request)
    with pytest.raises(WorkerError): worker.request('say','bot',message='hello')
    assert calls==[2.5]
    with pytest.raises(WorkerError): worker.request('say','bot',message='hello')
    assert calls==[2.5]  # No retry/publication after expiry.


def test_activity_wait_rejects_late_received_success(monkeypatch):
    clock=[10.0]; monkeypatch.setattr(bridge.time,'monotonic',lambda:clock[0])
    worker=object.__new__(bridge.ActivityWorker); worker.activity_deadline=15; worker.deadline_scale=1
    def wait(self,bot,predicate,description,timeout=30):
        assert timeout==5
        clock[0]=16
        return {'phase':'ready'}
    monkeypatch.setattr(Worker,'wait_state',wait)
    with pytest.raises(WorkerError): worker.wait_state('bot',lambda s:True,'ready')


def test_prepare_development_opt_in_is_strict_before_inputs():
    from .prepare_client_smoke import prepare
    with pytest.raises(ValueError,match='explicit boolean'):
        prepare('not-read','not-read','not-created',development_check=1)


def test_expired_activity_does_not_start_native_worker(tmp_path,monkeypatch):
    monkeypatch.setattr(bridge.time,'monotonic',lambda:10)
    with pytest.raises(WorkerError): bridge.ActivityWorker(tmp_path/'missing',tmp_path/'artifacts',deadline=9)
    assert not (tmp_path/'artifacts').exists()
