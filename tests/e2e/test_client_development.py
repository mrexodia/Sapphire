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
    continuity={'verified':True,
        'scope':'unchanged-received-spawn-token-on-persistent-observer-not-server-session-proof',
        'observer':'witness','observer_entity_id':2,'viewer_entity_id':3,'presence_token':105}
    effect={'source':1,'target':1,'action':3,'kind':1,'request':7,'result':0,
        'source_effects':[],'effects':[{'type':18,'value':50,'flag':128,'args':[0,0,30]}]}
    sprint={'requested':True,'verified':True,
        'scope':'one-self-sprint-received-effect-and-zero-tp-not-speed-expiry-or-cooldown-readiness',
        'identities':[{'name':'bot mover','entity_id':1,'character_id':11},
                      {'name':'bot witness','entity_id':2,'character_id':12}],
        'request':7,'tp_before':100,
        'baselines':[{'seq':10,'histories':{'effects':[],'starts':[],'hud_params':[]}},
                     {'seq':11,'histories':{'effects':[],'starts':[],'hud_params':[]}}],
        'receipts':[{'effect':copy.deepcopy(effect),'zero_tp':{'target':1,'hp':94,'hp_max':94,
                       'mp':52,'mp_max':52,'tp':0},
                     'start':{'source':1,'action':3,'group':56,'recast_centiseconds':3000},
                     'received_seq':20},
                    {'effect':copy.deepcopy(effect),'zero_tp':{'target':1,'hp':94,'hp_max':94,
                       'mp':52,'mp_max':52,'tp':0},'start':None,'received_seq':21}]}
    containers=[0,1,2,3,1000,2000]
    equipped_rows={'1000:0':{'storage':1000,'slot':0,'id':1601,'count':1},
                   '1000:3':{'storage':1000,'slot':3,'id':2983,'count':1}}
    unequipped_rows={'1000:0':{'storage':1000,'slot':0,'id':1601,'count':1},
                     '0:0':{'storage':0,'slot':0,'id':2983,'count':1}}
    def projection(rows, sequence):
        return {'containers':list(containers),'inventory':copy.deepcopy(rows),
                'received_sequence':sequence}
    reconnect={'requested':True,'verified':True,'scope':'fresh-login-position-not-world-restart',
        'identity_before':{'name':'bot mover','entity_id':1,'character_id':11},
        'identity_after':{'name':'bot mover','entity_id':1,'character_id':11},
        'territory':130,'expected_position':[0,0,0],'witness_before':[0,0,0],
        'received_after':[0,0,0],'witness_after':[0,0,0],
        'old_server_close_observed':True,'independent_despawn_observed':True,
        'post_login_say_observed':True,'world_restart_performed':False}
    equipment={'requested':True,'verified':True,
        'identity':{'name':'bot mover','entity_id':1,'character_id':11},
        'scope':'starter-body-slot-count-roundtrip-not-item-instances-or-world-restart',
        'reconnects_required':3,
        'mutation_observation':'fresh-login-not-current-session-acknowledgement',
        'before':projection(equipped_rows,30),'class_job':1,
        'unequip_expected':copy.deepcopy(unequipped_rows),'unequip_publication_attempted':True,
        'unequip_receipt':{'context':1,'operation':8,'acknowledged':True,
                           'inventory_change_verified':False},
        'unequip_reconnect':copy.deepcopy(reconnect),'unequipped':projection(unequipped_rows,31),
        'before_reequip':projection(unequipped_rows,32),'reequip_publication_attempted':True,
        'reequip_receipt':{'context':2,'operation':8,'acknowledged':True,
                           'inventory_change_verified':False},
        'reequip_reconnect':copy.deepcopy(reconnect),'reequipped':projection(equipped_rows,33)}
    return {'status':'passed','scope':'shared-development-not-acceptance','lease_retained':False,
            'entities':[1,2],'territory':130,
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
            'run_deadline':{'enabled':True,'limit_seconds':300,'expired':False,
                'session_work_completed_within_budget':True,
                'scope':'cooperative-success-deadline-not-hard-process-limit',
                'cleanup_may_exceed_deadline':True},
            'administrative_preparation_wait_enabled':False,'database_access':False,
            'world_restart_performed':False,'movement_waypoints_per_cycle':2,
            **{key:{'requested':True,'verified':True} for key in ('party_verification','tell_verification','reconnect_verification')},
            'sprint_verification':sprint,'equipment_verification':equipment,
            'inventory_verification':{'requested':True,'verified':True,
                'scope':'fresh-login-slot-catalog-counts-not-item-instances-or-world-restart',
                'before':projection(unequipped_rows,120),'after':projection(unequipped_rows,118),
                'changed_slots':[]},
            'viewer_verification':{'requested':True,'verified':True,'viewer_login_or_control_performed':False,
                'continuous_presence':copy.deepcopy(continuity),
                'start':{'identity':copy.deepcopy(identity)},
                'finish':{'identity':copy.deepcopy(identity),
                          'continuous_presence':copy.deepcopy(continuity)}}}


def test_report_requires_all_subchecks_and_same_non_gm_viewer():
    report=completed(); proof=bridge.require_graphical_check(report,'Tester Viewer',3)
    assert proof['status']=='passed' and proof['rendered_bot_actions_verified'] is False
    assert proof['continuous_presence']==report['viewer_verification']['continuous_presence']
    assert proof['sprint_scope']==report['sprint_verification']['scope']
    assert proof['equipment_scope']==report['equipment_verification']['scope']
    for key in ('party_verification','tell_verification','reconnect_verification','inventory_verification',
                'sprint_verification','equipment_verification','viewer_verification'):
        wrong=copy.deepcopy(report); wrong[key]['verified']=False
        with pytest.raises(DevelopmentError): bridge.require_graphical_check(wrong,'Tester Viewer',3)
    for stage in ('start','finish'):
        wrong=copy.deepcopy(report); wrong['viewer_verification'][stage]['identity']['entity_id']=999
        with pytest.raises(DevelopmentError): bridge.require_graphical_check(wrong,'Tester Viewer',3)


@pytest.mark.parametrize('field,value',[('status','failed'),('lease_retained',True),('worker_closed',False),
    ('worker_exit',None),('lease_snapshot',None),('lease_snapshot_matches_run_state',False),
    ('run_deadline',None),('inventory_verification',None),('sprint_verification',None),
    ('equipment_verification',None),
    ('administrative_preparation_wait_enabled',True),('database_access',True),
    ('world_restart_performed',True),('movement_waypoints_per_cycle',0),('territory',141)])
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


@pytest.mark.parametrize('field,value',[
    ('enabled',False),('enabled',1),('limit_seconds',True),('limit_seconds',0),
    ('limit_seconds',901),('expired',True),('session_work_completed_within_budget',False),
    ('scope','hard-timeout'),('cleanup_may_exceed_deadline',False)])
def test_graphical_bridge_requires_exact_successful_run_deadline(field,value):
    report=completed();report['run_deadline'][field]=value
    with pytest.raises(DevelopmentError):
        bridge.require_graphical_check(report,'Tester Viewer',3)


def test_graphical_bridge_rejects_malformed_inventory_receipt():
    mutations=(
        lambda value: value.update(scope='wrong'),
        lambda value: value.update(changed_slots=['1000:0']),
        lambda value: value.pop('before'),
        lambda value: value.update(before=None),
        lambda value: value['before'].update(containers=[0,1,2,3,2000,1000]),
        lambda value: value['before'].update(received_sequence=True),
        lambda value: value['before']['inventory']['1000:0'].update(extra=True),
        lambda value: value['before']['inventory']['1000:0'].update(id=True),
        lambda value: value['after']['inventory']['1000:0'].update(count=2),
    )
    for mutate in mutations:
        report=completed();mutate(report['inventory_verification'])
        with pytest.raises(DevelopmentError):
            bridge.require_graphical_check(report,'Tester Viewer',3)


def test_graphical_bridge_rejects_malformed_equipment_receipt():
    mutations=(
        lambda report: report['equipment_verification'].update(scope='appearance-proof'),
        lambda report: report['equipment_verification'].update(reconnects_required=True),
        lambda report: report['equipment_verification']['identity'].update(entity_id=2),
        lambda report: report['equipment_verification'].update(class_job=True),
        lambda report: report['equipment_verification']['before']['inventory'].pop('1000:3'),
        lambda report: report['equipment_verification']['unequip_expected'].pop('0:0'),
        lambda report: report['equipment_verification']['unequipped']['inventory'].pop('0:0'),
        lambda report: report['equipment_verification']['reequipped']['inventory'].pop('1000:3'),
        lambda report: report['equipment_verification']['unequip_receipt'].update(operation=True),
        lambda report: report['equipment_verification']['reequip_receipt'].update(acknowledged=False),
        lambda report: report['equipment_verification']['unequip_reconnect'].update(old_server_close_observed=False),
        lambda report: report['equipment_verification']['reequip_reconnect'].update(received_after=[2,0,0]),
        lambda report: report['inventory_verification']['before']['inventory'].pop('0:0'),
        lambda report: report['equipment_verification'].update(extra=True),
    )
    for mutate in mutations:
        report=completed();mutate(report)
        with pytest.raises(DevelopmentError):
            bridge.require_graphical_check(report,'Tester Viewer',3)


def test_graphical_bridge_rejects_malformed_sprint_receipt():
    mutations=(
        lambda report: report['sprint_verification'].update(scope='speed-proof'),
        lambda report: report['sprint_verification'].update(request=True),
        lambda report: report['sprint_verification'].update(tp_before=49),
        lambda report: report['sprint_verification']['identities'][0].update(entity_id=2),
        lambda report: report['sprint_verification']['identities'][1].update(character_id=11),
        lambda report: report['sprint_verification']['baselines'][0].update(seq=True),
        lambda report: report['sprint_verification']['baselines'][0]['histories'].update(extra=[]),
        lambda report: report['sprint_verification']['receipts'][0]['effect'].update(target=2),
        lambda report: report['sprint_verification']['receipts'][0]['effect'].update(kind=True),
        lambda report: report['sprint_verification']['receipts'][1]['zero_tp'].update(tp=False),
        lambda report: report['sprint_verification']['receipts'][0].update(start=None),
        lambda report: report['sprint_verification']['receipts'][1].update(received_seq=11),
        lambda report: report['sprint_verification'].update(extra=True),
    )
    for mutate in mutations:
        report=completed();mutate(report)
        with pytest.raises(DevelopmentError):
            bridge.require_graphical_check(report,'Tester Viewer',3)


def test_graphical_bridge_rejects_missing_or_changed_continuity():
    mutations=(
        lambda report: report['viewer_verification'].pop('continuous_presence'),
        lambda report: report['viewer_verification']['continuous_presence'].update(verified=False),
        lambda report: report['viewer_verification']['continuous_presence'].update(scope='server-session-proof'),
        lambda report: report['viewer_verification']['continuous_presence'].update(observer='mover'),
        lambda report: report['viewer_verification']['continuous_presence'].update(observer_entity_id=1),
        lambda report: report['viewer_verification']['continuous_presence'].update(viewer_entity_id=4),
        lambda report: report['viewer_verification']['continuous_presence'].update(presence_token=True),
        lambda report: report['viewer_verification']['continuous_presence'].update(extra=True),
        lambda report: report.update(entities=[1,1]),
        lambda report: report['viewer_verification']['finish'].update(continuous_presence={}),
    )
    for mutate in mutations:
        report=completed();mutate(report)
        with pytest.raises(DevelopmentError):
            bridge.require_graphical_check(report,'Tester Viewer',3)


def test_graphical_bridge_rejects_changed_deadline_shape():
    for mutate in (lambda row: row.pop('expired'), lambda row: row.update(extra=True)):
        report=completed();mutate(report['run_deadline'])
        with pytest.raises(DevelopmentError):
            bridge.require_graphical_check(report,'Tester Viewer',3)


def test_nested_development_budget_stays_inside_activity_deadline(monkeypatch):
    monkeypatch.setattr(bridge.time,'monotonic',lambda:100.0)
    assert bridge.development_run_budget(1002.0)==900
    assert bridge.development_run_budget(1000.2)==899
    assert bridge.development_run_budget(102.0)==1
    for deadline in (101.999, float('inf'), float('nan')):
        with pytest.raises(WorkerError):
            bridge.development_run_budget(deadline)


def test_graphical_scenario_forwards_nested_deadline_and_exact_flags(monkeypatch,tmp_path):
    monkeypatch.setattr(bridge.time,'monotonic',lambda:100.0)
    calls=[]
    login=object()
    def runner(*args,**kwargs):
        calls.append((args,kwargs))
        return {'status':'synthetic'}
    result=bridge.run_graphical_development(
        runner,{'profile':True},tmp_path/'output',viewer_name='Tester Viewer',
        activity_deadline=500.8,login=login)
    assert result=={'status':'synthetic'} and len(calls)==1
    args,kwargs=calls[0]
    assert args==({'profile':True},tmp_path/'output')
    assert kwargs['confirmed'] is True and kwargs['verify_party'] is True
    assert kwargs['verify_tell'] is True and kwargs['verify_reconnect'] is True
    assert (kwargs['verify_inventory'] is True and kwargs['verify_sprint'] is True
            and kwargs['verify_equipment'] is True)
    assert kwargs['viewer_name']=='Tester Viewer' and kwargs['login'] is login
    assert kwargs['max_seconds']==399 and callable(kwargs['worker_factory'])


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
