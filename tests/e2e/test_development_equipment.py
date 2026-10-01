"""Synthetic contracts, not evidence of live inventory/persistence/visual changes."""
import copy

import pytest

from . import run_development
from .support import development_equipment as equipment
from .support.development import DevelopmentError
from .support.development_party import EMPTY_PARTY
from .test_development import profile
from .test_development_inventory import InventoryWorker


class EquipmentWorker(InventoryWorker):
    def __init__(self, failure=None):
        super().__init__()
        self.equipment_failure, self.operations = failure, []
        for state in self.states.values():
            state.update(party=copy.deepcopy(EMPTY_PARTY), pending_party_invite=None, party_invite_result=None)
            state['rewards'].update(class_job=1, operation_batches=[])
            state['rewards']['inventory']['1000:3'] = dict(equipment.BODY)
        s = self.states['mover']; inv = s['rewards']['inventory']
        if failure == 'occupied_destination': inv['0:0'] = dict(equipment.BAG)
        if failure == 'wrong_body': inv['1000:3']['id'] = 2967
        if failure == 'wrong_count': inv['1000:3']['count'] = 2
        if failure == 'unsupported_class': s['rewards']['class_job'] = 19
        if failure == 'party': s['party']['id'] = 99
        if failure == 'invite': s['pending_party_invite'] = {'character_id': 999}
        if failure == 'incomplete': s['rewards']['containers']['1000'] = False
        self.original = copy.deepcopy(s)

    def request(self, method, bot=None, **args):
        f = self.equipment_failure
        if method == 'capabilities':
            return {'methods': [] if f == 'old_worker' else sorted(equipment.METHODS)}
        if method not in equipment.METHODS:
            if method == 'logout' and bot == 'mover':
                self.original = copy.deepcopy(self.states['mover'])  # Model persistence only.
            result = super().request(method, bot, **args)
            if method == 'login' and bot == 'mover-reconnected':
                s = self.states[bot]; s['rewards']['operation_batches'] = []
                if f == 'changed_on_login': s['rewards']['inventory']['0:0']['id'] = 999
                if f == 'class_changed': s['rewards']['class_job'] = 2
            return result
        self.operations.append(method)
        s = self.states[bot]; inv = s['rewards']['inventory']
        unequip = method == 'request_item_unequip'
        assert bot == ('mover' if unequip else 'mover-reconnected')
        assert args == ({'gear_slot': 3, 'destination_storage': 0, 'destination_slot': 0, 'expected_item': 2983}
                        if unequip else {'gear_slot': 3, 'storage': 0, 'slot': 0, 'expected_item': 2983})
        context = True if f == 'invalid_context' else 1  # Contexts may repeat in a new session.
        if f not in {'unequip_ack_only' if unequip else 'reequip_ack_only'}:
            if unequip:
                del inv['1000:3']; inv['0:0'] = dict(equipment.BAG)
            else:
                del inv['0:0']; inv['1000:3'] = dict(equipment.BODY)
        if f == 'changed_currency': inv['2000:0']['count'] += 1
        if f == 'wrong_destination' and unequip: inv['0:0']['slot'] = 1
        if f != 'stale_sequence': s['seq'] += 1
        if f != 'missing_ack':
            s['rewards']['operation_batches'].append({'context': context, 'operation': 8, 'error': 0})
        if f == 'late_publication': self.clock[0] += 11
        return {'context': context}

    def wait_state(self, bot, predicate, description, timeout=30):
        result = super().wait_state(bot, predicate, description, timeout)
        if self.equipment_failure == 'late_observation' and description == 'exact received equipment round-trip projection':
            self.clock[0] += 11
        if self.equipment_failure == 'changed_before_reequip' and bot == 'mover-reconnected' and description == 'exact say':
            self.states[bot]['rewards']['inventory']['0:0']['id'] = 999
        return result

    def snapshot(self, bot):
        if bot == 'mover-reconnected' and self.equipment_failure == 'changed_before_reequip':
            self.states[bot]['rewards']['inventory']['0:0']['id'] = 999
        return super().snapshot(bot)


def execute(profile, tmp_path, failure=None, enabled=True, worker=None):
    fake, logins = worker or EquipmentWorker(failure), []
    def login(*args):
        logins.append(True)
        return {'lobbyHost': '127.0.0.1', 'lobbyPort': 54994, 'sId': 'private'}
    report = run_development.run(profile, tmp_path / 'run', confirmed=True,
        verify_reconnect=True, verify_inventory=True, verify_equipment=enabled,
        worker_factory=lambda *_: fake, login=login, lease_root=tmp_path / 'leases')
    return report, fake, logins


def test_normal_equipment_roundtrip_wraps_nonempty_bag_reconnect(profile, tmp_path):
    report, fake, logins = execute(profile, tmp_path)
    assert report['status'] == 'passed' and fake.closed and not report['lease_retained']
    assert len(logins) == 3
    p = report['equipment_verification']; inventory = report['inventory_verification']
    assert p['verified'] and inventory['verified']
    assert p['before']['inventory'] == p['reequipped']['inventory']
    assert p['unequipped']['inventory'] == inventory['before']['inventory'] == inventory['after']['inventory']
    assert inventory['after']['inventory']['0:0'] == equipment.BAG
    assert '1000:3' not in inventory['after']['inventory']
    assert p['before_reequip']['received_sequence'] < p['unequipped']['received_sequence']
    assert p['reequipped']['received_sequence'] > p['before_reequip']['received_sequence']
    assert fake.operations == ['request_item_unequip', 'request_item_reequip_starter']
    assert p['unequip_receipt']['inventory_change_verified'] is False
    assert p['reequip_receipt']['inventory_change_verified'] is False
    fake.states['mover-reconnected']['rewards']['inventory']['1000:3']['count'] = 99
    assert p['reequipped']['inventory']['1000:3']['count'] == 1


@pytest.mark.parametrize('failure,count', [
    ('old_worker', 0), ('occupied_destination', 0), ('wrong_body', 0), ('wrong_count', 0),
    ('unsupported_class', 0), ('party', 0), ('invite', 0), ('incomplete', 0),
    ('unequip_ack_only', 1), ('reequip_ack_only', 2), ('missing_ack', 1), ('stale_sequence', 1),
    ('changed_currency', 1), ('wrong_destination', 1), ('changed_on_login', 1),
    ('class_changed', 1), ('changed_before_reequip', 1), ('invalid_context', 1)])
def test_failed_operation_never_retries_or_restores(profile, tmp_path, failure, count):
    report, fake, logins = execute(profile, tmp_path, failure)
    assert report['status'] == 'failed' and report['lease_retained'] and fake.closed
    assert not report['equipment_verification']['verified']
    assert len(fake.operations) == count and len(set(fake.operations)) == count
    assert report['error_type'] == 'DevelopmentError'
    if failure == 'old_worker': assert not logins
    assert len(list((tmp_path / 'leases').glob('*.lock'))) == 2
    if count:
        assert report['equipment_verification']['unequip_publication_attempted'] is True
        assert report['equipment_verification']['before']
    if failure == 'changed_before_reequip':
        assert report['failure_stage'] == 'equipment_before_reequip'


def test_explicit_prerequisites_and_default_unchanged(profile, tmp_path):
    report, fake, _ = execute(profile, tmp_path, enabled=False)
    assert report['status'] == 'passed' and fake.operations == []
    for args in ({'verify_equipment': True}, {'verify_equipment': True, 'verify_reconnect': True},
                 {'verify_equipment': 1, 'verify_reconnect': True, 'verify_inventory': True}):
        with pytest.raises(DevelopmentError):
            run_development.run(profile, tmp_path / 'invalid', confirmed=True, **args)
    assert not (tmp_path / 'invalid').exists()


@pytest.mark.parametrize('failure', ['late_publication', 'late_observation'])
def test_late_mutation_is_failure_without_recovery(profile, tmp_path, monkeypatch, failure):
    now = [0.0]; monkeypatch.setattr(equipment.time, 'monotonic', lambda: now[0])
    fake = EquipmentWorker(failure); fake.clock = now
    report, fake, _ = execute(profile, tmp_path, worker=fake)
    assert report['status'] == 'failed' and len(fake.operations) == 1
    assert report['lease_retained'] and not report['equipment_verification']['verified']
