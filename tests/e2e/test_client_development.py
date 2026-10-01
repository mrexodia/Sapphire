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
    run_id='a'*32
    tell={'requested':True,'verified':True,'scope':'visible-two-bot-tell-not-general-messaging',
        'received_tells':[]}
    tell_identities=[{'name':'bot mover','entity_id':1,'character_id':11},
                     {'name':'bot witness','entity_id':2,'character_id':12}]
    for index in (0,1):
        sender,recipient=tell_identities[index],tell_identities[1-index]
        baseline,sequence=40+index*2,41+index*2
        tell['received_tells'].append({'sender':copy.deepcopy(sender),'recipient':copy.deepcopy(recipient),
            'baseline_seq':baseline,'received_seq':sequence,
            'received':{'actor':sender['entity_id'],'character_id':sender['character_id'],
                'message':f'Sapphire dev {run_id} tell {index} '+str(index)*16,
                'name':sender['name'],'party_id':0,'token':sequence}})
    party_id,channel=99,88
    party={'requested':True,'verified':True,'scope':'owned-two-bot-party-not-general-social',
        'identities':copy.deepcopy(tell_identities),
        'party':{'id':party_id,'chat_channel':channel,'count':2,'leader_index':0,
            'members':[{'entity_id':row['entity_id'],'character_id':row['character_id'],
                        'name':row['name'],'territory':130,'class_job':1,'level':1}
                       for row in tell_identities]},
        'invitation_receipt':{'result':0,'target':'bot witness'},
        'received_chat':[{'actor':row['entity_id'],'channel':channel,
            'character_id':row['character_id'],'message':f'Sapphire dev {run_id} party {index}',
            'name':row['name'],'party_id':party_id,'token':50+index}
            for index,row in enumerate(tell_identities)],
        'both_empty_after_disband':True}
    movement={'requested':True,'verified':True,
        'scope':'independent-witness-waypoints-not-server-authority-or-rendering',
        'cycles':1,'authored_route':[[0,0,0],[1,0,0]],
        'mover_entity_id':1,'witness_entity_id':2,'speed':2.0,
        'baseline_witness_sequence':5,
        'observations':[{'cycle':0,'step':0,'target':[1,0,0],
                         'received_position':[1,0,0],'witness_sequence':6},
                        {'cycle':0,'step':1,'target':[0,0,0],
                         'received_position':[0,0,0],'witness_sequence':7}]}
    def viewer_checkpoint(stage, mover_name, mover_token, witness_token, continuous=None):
        observers=(mover_name,'witness');tokens={mover_name:mover_token,'witness':witness_token}
        message=f'Sapphire viewer {run_id[:8]} {stage} '+('1' if stage=='start' else '2')*32
        rows=[{'entity_id':3,'name':'Tester Viewer','gm_rank':0,
               'position':[0,0,0],'presence_token':tokens[observer]} for observer in observers]
        result={'verified':True,'stage':stage,'identity':copy.deepcopy(identity),
            'presence_tokens':tokens,'initial_observations':copy.deepcopy(rows),
            'received_replies':[{'observer':observer,'viewer':copy.deepcopy(row),
                'message':message,'baseline_sequence':200+index*2,
                'received_sequence':201+index*2}
                for index,(observer,row) in enumerate(zip(observers,rows))]}
        if continuous is not None: result['continuous_presence']=copy.deepcopy(continuous)
        return result
    viewer_start=viewer_checkpoint('start','mover',104,105)
    viewer_finish=viewer_checkpoint('finish','mover-equipment-reequipped',7,105,continuity)
    return {'version':1,'status':'passed','scope':'shared-development-not-acceptance',
            'server_identity_verified':False,'server_processes_owned':False,
            'database_access':False,'account_reset_performed_by_runner':False,
            'administrative_command_execution_attested':False,'protocol':'sapphire-3.3',
            'worker_sha256':'d'*64,'lease_retained':False,
            'entities':[1,2],'territory':130,'run_id':run_id,'cycles':1,
            'catalog_sha256':'c'*64,
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
            'administrative_preparation_wait_enabled':False,
            'world_restart_performed':False,'movement_waypoints_per_cycle':2,
            'movement_verification':movement,'party_verification':party,
            'decline_verification':{'requested':False,'verified':False},
            'reconnect_verification':copy.deepcopy(reconnect),
            'tell_verification':tell,'sprint_verification':sprint,'equipment_verification':equipment,
            'inventory_verification':{'requested':True,'verified':True,
                'scope':'fresh-login-slot-catalog-counts-not-item-instances-or-world-restart',
                'before':projection(unequipped_rows,120),'after':projection(unequipped_rows,118),
                'changed_slots':[]},
            'viewer_verification':{'requested':True,'verified':True,
                'scope':'two-endpoint-say-and-persistent-witness-presence-not-rendering',
                'viewer_login_or_control_performed':False,
                'continuous_presence':copy.deepcopy(continuity),
                'start':viewer_start,'finish':viewer_finish}}


def declined():
    report=completed()
    report['catalog_sha256']=None
    report['movement_waypoints_per_cycle']=0
    report['movement_verification']={'requested':False,'verified':False}
    for key in ('reconnect_verification','inventory_verification','party_verification',
                'tell_verification','sprint_verification','equipment_verification'):
        report[key]={'requested':False,'verified':False}
    identities=[{'name':'bot mover','entity_id':1,'character_id':11},
                {'name':'bot witness','entity_id':2,'character_id':12}]
    report['decline_verification']={'requested':True,'verified':True,
        'scope':'dedicated-peer-decline-not-general-social','identities':identities,
        'invitation_result':{'result':0,'target':'bot witness'},
        'received_reply':{'result':0,'auth_type':1,'answer':0,'name':'bot mover'},
        'received_rejection':{'character_id':12,'auth_type':1,'result':5,'name':'bot witness'},
        'baseline_sequences':[10,11],'received_sequences':[14,13],
        'both_empty_after_decline':True}
    finish=report['viewer_verification']['finish']
    finish['presence_tokens']['mover']=finish['presence_tokens'].pop('mover-equipment-reequipped')
    finish['received_replies'][0]['observer']='mover'
    return report


def test_report_requires_all_subchecks_and_same_non_gm_viewer():
    report=completed(); proof=bridge.require_graphical_check(report,'Tester Viewer',3)
    assert proof['status']=='passed' and proof['rendered_bot_actions_verified'] is False
    assert proof['continuous_presence']==report['viewer_verification']['continuous_presence']
    assert proof['movement_scope']==report['movement_verification']['scope']
    assert proof['reconnect_scope']==report['reconnect_verification']['scope']
    assert proof['party_scope']==report['party_verification']['scope']
    assert proof['tell_scope']==report['tell_verification']['scope']
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
    ('world_restart_performed',True),('movement_waypoints_per_cycle',0),('territory',141),
    ('run_id','b'*31)])
def test_partial_or_wrong_scope_is_not_graphical_bridge_success(field,value):
    report=completed(); report[field]=value
    with pytest.raises(DevelopmentError): bridge.require_graphical_check(report,'Tester Viewer',3)


@pytest.mark.parametrize('field,value',[('version',True),('protocol','other'),('cycles',True),
    ('server_identity_verified',True),('server_processes_owned',True),
    ('account_reset_performed_by_runner',True),('administrative_command_execution_attested',True),
    ('worker_sha256','bad'),('catalog_sha256','bad')])
def test_graphical_checks_retain_exact_shared_runner_metadata(field,value):
    report=completed();report[field]=value
    with pytest.raises(DevelopmentError): bridge.require_graphical_check(report,'Tester Viewer',3)
    decline=declined();decline[field]=(None if field=='catalog_sha256' else value)
    if field=='catalog_sha256':
        decline[field]='c'*64  # The route-free decline must retain an absent catalog.
    with pytest.raises(DevelopmentError):
        bridge.require_graphical_decline_check(decline,'Tester Viewer',3)


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


def test_separate_graphical_decline_receipt_passes_without_foreign_scenarios():
    report=declined(); proof=bridge.require_graphical_decline_check(report,'Tester Viewer',3)
    assert proof['status']=='passed' and proof['decline_scope']==report['decline_verification']['scope']
    assert proof['rendered_bot_actions_verified'] is False


def test_graphical_run_pair_binds_same_dedicated_characters_and_distinct_runs():
    comprehensive, decline = completed(), declined()
    decline['run_id'] = 'b'*32
    proof = bridge.require_graphical_run_pair(
        comprehensive, decline, ['bot mover', 'bot witness'], 'd'*64)
    assert proof == {'verified':True,
        'scope':'same-dedicated-bot-identities-across-distinct-runs-not-offline-or-reset-proof',
        'comprehensive_run_id':'a'*32, 'decline_run_id':'b'*32,
        'worker_sha256':'d'*64,
        'identities':comprehensive['sprint_verification']['identities']}


def test_graphical_run_pair_rejects_reused_or_foreign_provenance():
    mutations = (
        lambda comprehensive, decline: decline.update(run_id='a'*32),
        lambda comprehensive, decline: decline.update(worker_sha256='e'*64),
        lambda comprehensive, decline: decline.update(entities=[2,1]),
        lambda comprehensive, decline: decline['decline_verification']['identities'][0].update(
            character_id=99),
        lambda comprehensive, decline: comprehensive['sprint_verification']['identities'][1].update(
            name='foreign'),
        lambda comprehensive, decline: comprehensive.update(entities=[1,1]),
    )
    for mutate in mutations:
        comprehensive, decline = completed(), declined()
        decline['run_id'] = 'b'*32
        mutate(comprehensive, decline)
        with pytest.raises(DevelopmentError):
            bridge.require_graphical_run_pair(
                comprehensive, decline, ['bot mover', 'bot witness'], 'd'*64)
    with pytest.raises(DevelopmentError):
        bridge.require_graphical_run_pair(
            completed(), {**declined(), 'run_id':'b'*32},
            ['bot mover', 'foreign'], 'd'*64)


def test_graphical_decline_rejects_malformed_or_mixed_receipts():
    mutations=(
        lambda report: report.update(status='failed'),
        lambda report: report.update(lease_retained=True),
        lambda report: report.update(movement_waypoints_per_cycle=2),
        lambda report: report['movement_verification'].update(requested=True),
        lambda report: report['party_verification'].update(requested=True),
        lambda report: report['decline_verification'].update(scope='general-social-proof'),
        lambda report: report['decline_verification'].update(both_empty_after_decline=False),
        lambda report: report['decline_verification']['identities'][0].update(entity_id=2),
        lambda report: report['decline_verification']['invitation_result'].update(target='foreign'),
        lambda report: report['decline_verification']['received_reply'].update(answer=True),
        lambda report: report['decline_verification']['received_rejection'].update(result=0),
        lambda report: report['decline_verification']['baseline_sequences'].__setitem__(0,True),
        lambda report: report['decline_verification']['received_sequences'].__setitem__(1,11),
        lambda report: report['decline_verification'].update(extra=True),
        lambda report: report['viewer_verification']['finish']['received_replies'][0].update(
            observer='mover-equipment-reequipped'),
    )
    for mutate in mutations:
        report=declined();mutate(report)
        with pytest.raises(DevelopmentError):
            bridge.require_graphical_decline_check(report,'Tester Viewer',3)


def test_comprehensive_graphical_run_rejects_embedded_decline():
    report=completed();report['decline_verification']=declined()['decline_verification']
    with pytest.raises(DevelopmentError):
        bridge.require_graphical_check(report,'Tester Viewer',3)


def test_graphical_bridge_rejects_malformed_movement_receipt():
    mutations=(
        lambda report: report['movement_verification'].update(scope='server-authority-proof'),
        lambda report: report['movement_verification'].update(cycles=True),
        lambda report: report['movement_verification'].update(mover_entity_id=True),
        lambda report: report['movement_verification'].update(witness_entity_id=1),
        lambda report: report['movement_verification'].update(speed=2),
        lambda report: report['movement_verification'].update(baseline_witness_sequence=True),
        lambda report: report['movement_verification']['authored_route'].append([10,0,0]),
        lambda report: report['movement_verification']['observations'].pop(),
        lambda report: report['movement_verification']['observations'][0].update(cycle=True),
        lambda report: report['movement_verification']['observations'][0].update(target=[0,0,0]),
        lambda report: report['movement_verification']['observations'][0].update(received_position=[2,0,0]),
        lambda report: report['movement_verification']['observations'][1].update(witness_sequence=6),
        lambda report: report['reconnect_verification'].update(expected_position=[1,0,0]),
        lambda report: report.update(catalog_sha256='bad'),
        lambda report: report['movement_verification'].update(extra=True),
    )
    for mutate in mutations:
        report=completed();mutate(report)
        with pytest.raises(DevelopmentError):
            bridge.require_graphical_check(report,'Tester Viewer',3)


def test_graphical_bridge_rejects_malformed_main_reconnect_receipt():
    mutations=(
        lambda report: report['reconnect_verification'].update(scope='world-restart-proof'),
        lambda report: report['reconnect_verification']['identity_before'].update(entity_id=True),
        lambda report: report['reconnect_verification'].update(identity_after={}),
        lambda report: report['reconnect_verification'].update(territory=True),
        lambda report: report['reconnect_verification'].update(expected_position=[float('nan'),0,0]),
        lambda report: report['reconnect_verification'].update(witness_before=[1,0,0]),
        lambda report: report['reconnect_verification'].update(old_server_close_observed=False),
        lambda report: report['reconnect_verification'].update(independent_despawn_observed=False),
        lambda report: report['reconnect_verification'].update(post_login_say_observed=False),
        lambda report: report['reconnect_verification'].update(world_restart_performed=True),
        lambda report: report['reconnect_verification'].update(extra=True),
    )
    for mutate in mutations:
        report=completed();mutate(report)
        with pytest.raises(DevelopmentError):
            bridge.require_graphical_check(report,'Tester Viewer',3)


def test_graphical_bridge_rejects_malformed_party_receipt():
    mutations=(
        lambda report: report['party_verification'].update(scope='general-social-proof'),
        lambda report: report['party_verification'].update(both_empty_after_disband=False),
        lambda report: report['party_verification']['identities'][0].update(entity_id=2),
        lambda report: report['party_verification']['party'].update(id=True),
        lambda report: report['party_verification']['party'].update(count=True),
        lambda report: report['party_verification']['party']['members'][0].update(entity_id=True),
        lambda report: report['party_verification']['party']['members'][1].update(territory=141),
        lambda report: report['party_verification']['invitation_receipt'].update(target='foreign'),
        lambda report: report['party_verification']['received_chat'].pop(),
        lambda report: report['party_verification']['received_chat'][0].update(channel=1),
        lambda report: report['party_verification']['received_chat'][0].update(token=True),
        lambda report: report['party_verification']['received_chat'][1].update(message='stale'),
        lambda report: report['party_verification']['received_chat'][0].update(extra=True),
        lambda report: report['party_verification'].update(extra=True),
    )
    for mutate in mutations:
        report=completed();mutate(report)
        with pytest.raises(DevelopmentError):
            bridge.require_graphical_check(report,'Tester Viewer',3)


def test_graphical_bridge_rejects_malformed_tell_receipt():
    mutations=(
        lambda report: report['tell_verification'].update(scope='offline-message-proof'),
        lambda report: report['tell_verification']['received_tells'].pop(),
        lambda report: report['tell_verification']['received_tells'][0]['sender'].update(entity_id=2),
        lambda report: report['tell_verification']['received_tells'][1].update(recipient={}),
        lambda report: report['tell_verification']['received_tells'][0].update(baseline_seq=True),
        lambda report: report['tell_verification']['received_tells'][0].update(received_seq=40),
        lambda report: report['tell_verification']['received_tells'][0]['received'].update(actor=2),
        lambda report: report['tell_verification']['received_tells'][0]['received'].update(party_id=False),
        lambda report: report['tell_verification']['received_tells'][0]['received'].update(token=40),
        lambda report: report['tell_verification']['received_tells'][0]['received'].update(message='stale'),
        lambda report: report['tell_verification']['received_tells'][0]['received'].update(extra=True),
        lambda report: report['tell_verification'].update(extra=True),
    )
    for mutate in mutations:
        report=completed();mutate(report)
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


def test_graphical_bridge_rejects_malformed_viewer_checkpoints():
    mutations=(
        lambda report: report['viewer_verification'].update(scope='graphical-rendering-proof'),
        lambda report: report['viewer_verification']['start'].update(stage='finish'),
        lambda report: report['viewer_verification']['start']['presence_tokens'].update(mover=True),
        lambda report: report['viewer_verification']['start']['initial_observations'].pop(),
        lambda report: report['viewer_verification']['start']['initial_observations'][0].update(presence_token=999),
        lambda report: report['viewer_verification']['start']['received_replies'].pop(),
        lambda report: report['viewer_verification']['start']['received_replies'][0].update(observer='foreign'),
        lambda report: report['viewer_verification']['start']['received_replies'][0].update(baseline_sequence=True),
        lambda report: report['viewer_verification']['start']['received_replies'][0].update(received_sequence=20),
        lambda report: report['viewer_verification']['start']['received_replies'][0]['viewer'].update(gm_rank=False),
        lambda report: report['viewer_verification']['start']['received_replies'][0].update(message='stale'),
        lambda report: report['viewer_verification']['start'].update(extra=True),
        lambda report: report['viewer_verification']['finish']['received_replies'][0].update(
            observer='mover-reconnected'),
        lambda report: report['viewer_verification'].update(extra=True),
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


def test_graphical_decline_is_a_separate_fresh_bounded_run(monkeypatch,tmp_path):
    monkeypatch.setattr(bridge.time,'monotonic',lambda:100.0)
    calls=[];login=object();profile={'quest_catalog':'private-catalog','keep':'binding'}
    def runner(*args,**kwargs):
        calls.append((args,kwargs));return {'status':'synthetic'}
    result=bridge.run_graphical_decline(
        runner,profile,tmp_path/'decline',viewer_name='Tester Viewer',
        activity_deadline=500.8,login=login)
    assert result=={'status':'synthetic'} and profile['quest_catalog']=='private-catalog'
    args,kwargs=calls[0]
    assert args[0]=={'keep':'binding'} and args[1]==tmp_path/'decline'
    assert kwargs['confirmed'] is True and kwargs['verify_decline'] is True
    assert kwargs['viewer_name']=='Tester Viewer' and kwargs['login'] is login
    assert kwargs['max_seconds']==399 and callable(kwargs['worker_factory'])
    assert all(key not in kwargs for key in ('verify_party','verify_reconnect','verify_sprint'))


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
