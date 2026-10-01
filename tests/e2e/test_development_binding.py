"""Offline receipt association contracts; no current online/exclusive-state claim."""
import copy
import json
from pathlib import Path

import pytest

from . import prepare_development
from .support.development import DevelopmentError
from .support.development_binding import provisioning_binding, require_provisioning_binding
from .test_development_placement import preparation
from .test_development_provisioning import server, execute


def test_successful_provisioner_emits_secret_free_identity_association(server, tmp_path):
    report, _, _ = execute(server, tmp_path)
    private = json.loads((tmp_path / 'private.json').read_text())
    assert report['status'] == 'provisioned'
    require_provisioning_binding(private, report)
    assert len(report['provisioning_binding']['sha256']) == 64
    text = json.dumps(report['provisioning_binding'])
    for account in private['accounts']:
        assert account['password'] not in text and account['username'] not in text
    assert 'private-session' not in text


@pytest.mark.parametrize('change', ['api_port','lobby_port','username','character','account_order','entity_id','character_id','host_session'])
def test_planner_refuses_mixed_or_changed_association(preparation, change):
    private, report = preparation
    if change in {'api_port','lobby_port'}: private[change] += 1
    if change == 'username': private['accounts'][0]['username'] = 'e2e_different_owner'
    if change == 'character':
        private['accounts'][0]['character'] = 'Tester ZZZZZZZZZZZZ'
        report['accounts'][0]['character'] = private['accounts'][0]['character']
    if change == 'account_order': private['accounts'].reverse()
    if change in {'entity_id','character_id'}: report['accounts'][0][change] += 1000
    if change == 'host_session': private['host_session'] = {'id':'a'*32,'path':str(Path('/private/status.json').resolve())}
    with pytest.raises(DevelopmentError): prepare_development.placement_registry(private, report)


@pytest.mark.parametrize('binding', [None, {}, {'schema':'wrong','sha256':'a'*64}, {'schema':'development-provisioning-association-v1','sha256':True}])
def test_legacy_or_malformed_association_is_not_synthesized(preparation, binding):
    private, report = preparation
    report['provisioning_binding'] = binding
    original = copy.deepcopy(report)
    with pytest.raises(DevelopmentError): prepare_development.placement_registry(private, report)
    assert report == original


def test_password_worker_catalog_changes_do_not_reselect_accounts(preparation, tmp_path):
    private, report = preparation
    expected = copy.deepcopy(report['provisioning_binding'])
    private['accounts'][0]['password'] = 'rotated-private-password'
    private['accounts'][0]['username'] = 'e2e_' + private['accounts'][0]['username'][4:].upper()
    replacement = tmp_path / 'replacement-worker'; replacement.write_bytes(b'new worker')
    private['worker'] = str(replacement)
    private['quest_catalog'] = str(tmp_path / 'independently-validated-catalog.json')
    assert provisioning_binding(private, report['accounts']) == expected
    assert prepare_development.placement_registry(private, report)['bots'][0]['character_id'] == report['accounts'][0]['character_id']


def test_full_uint64_character_identity_is_not_rounded(preparation):
    private, report = preparation
    report['accounts'][0]['character_id'] = 2**54 + 1
    first = provisioning_binding(private, report['accounts'])
    report['accounts'][0]['character_id'] += 1
    assert provisioning_binding(private, report['accounts']) != first
