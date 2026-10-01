"""Bridge the owned manual graphical fixture to the separate normal-bot lane."""
import math
import time

from .development import (DevelopmentError, MOVEMENT_SCOPE, validate_profile, movement_route,
                          idle_state, position, received_character_identity,
                          require_normal_worker_exit)
from .worker import Worker, WorkerError
from .development_lease import require_clear_terminal_account_leases
from .development_inventory import CONTAINERS, SCOPE as INVENTORY_SCOPE
from .development_viewer import CONTINUITY_SCOPE, VIEWER_SCOPE, observe_viewer
from .development_sprint import HISTORIES as SPRINT_HISTORIES, SCOPE as SPRINT_SCOPE
from .development_equipment import BODY, BAG, SCOPE as EQUIPMENT_SCOPE
from .development_tell import SCOPE as TELL_SCOPE
from .development_party import EMPTY_PARTY, SCOPE as PARTY_SCOPE
from .development_decline import SCOPE as DECLINE_SCOPE


def development_run_budget(activity_deadline):
    """Nest an integer runner deadline strictly inside the graphical activity budget."""
    remaining = activity_deadline - time.monotonic()
    if not math.isfinite(remaining) or remaining < 2:
        raise WorkerError('graphical activity deadline cannot admit a development run')
    # The one-second margin keeps RunDeadline's later start from extending beyond
    # the already-running graphical deadline. ActivityWorker remains the outer cap.
    return min(900, math.floor(remaining) - 1)


class ActivityWorker(Worker):
    """Cap normal RPC/wait budgets by the guest activity deadline; never retry."""
    def __init__(self, executable, artifacts, *, deadline):
        self.activity_deadline = deadline
        if time.monotonic() >= deadline:
            raise WorkerError('graphical development activity deadline expired')
        super().__init__(executable, artifacts)

    def budget(self, timeout):
        remaining = self.activity_deadline - time.monotonic()
        if remaining <= 0:
            raise WorkerError('graphical development activity deadline expired')
        return min(timeout, remaining / self.deadline_scale)

    def request(self, method, bot=None, timeout=10, **args):
        result = super().request(method, bot, timeout=self.budget(timeout), **args)
        self.budget(1)  # Reject late success, not merely the next operation.
        return result

    def wait_state(self, bot, predicate, description, timeout=30):
        result = super().wait_state(bot, predicate, description, timeout=self.budget(timeout))
        self.budget(1)
        return result


def run_graphical_development(runner, profile, artifacts, *, viewer_name, activity_deadline, login):
    """Invoke the exact normal-bot scenario with nested and outer deadline guards."""
    budget = development_run_budget(activity_deadline)
    return runner(profile, artifacts, confirmed=True, verify_party=True, verify_tell=True,
                  verify_sprint=True, verify_reconnect=True, verify_inventory=True,
                  verify_equipment=True, viewer_name=viewer_name,
                  worker_factory=lambda executable, output: ActivityWorker(
                      executable, output, deadline=activity_deadline),
                  login=login, max_seconds=budget)


def run_graphical_decline(runner, profile, artifacts, *, viewer_name, activity_deadline, login,
                          viewer_finish_callback=None):
    """Run the mutually exclusive exact-peer decline in a second fresh bot session."""
    short_profile = dict(profile)
    short_profile.pop('quest_catalog', None)  # No repeated movement; decline is a distinct fresh run.
    budget = development_run_budget(activity_deadline)
    return runner(short_profile, artifacts, confirmed=True, verify_decline=True,
                  viewer_name=viewer_name, viewer_finish_callback=viewer_finish_callback,
                  worker_factory=lambda executable, output: ActivityWorker(
                      executable, output, deadline=activity_deadline),
                  login=login, max_seconds=budget)


def development_profile(env, witness, peer, viewer, catalog):
    accounts = [witness, peer]
    for key in ('username', 'name'):
        values = [row[key].casefold() for row in [*accounts, viewer]]
        if len(set(values)) != 3:
            raise DevelopmentError('graphical viewer and both bot fixtures must be separate')
    profile = {'version':1, 'mode':'shared-development', 'protocol':'sapphire-3.3',
               'worker':str(env.worker), 'api_port':env.api_port, 'lobby_port':env.lobby_port,
               'territory':130, 'quest_catalog':str(catalog),
               'accounts':[{'username':row['username'], 'password':row['password'], 'character':row['name']}
                           for row in accounts]}
    validate_profile(profile)
    movement_route(profile)  # Reject unsupported/malformed source corridors before bot login.
    return profile


def require_inventory_projection(value):
    if (not isinstance(value, dict) or set(value) != {'containers', 'inventory', 'received_sequence'}
            or value.get('containers') != list(CONTAINERS)
            or type(value.get('received_sequence')) is not int
            or not 0 <= value['received_sequence'] < 2**64
            or not isinstance(value.get('inventory'), dict)):
        raise DevelopmentError('malformed graphical reconnect inventory projection')
    for key, row in value['inventory'].items():
        if (not isinstance(key, str) or not isinstance(row, dict)
                or set(row) != {'storage', 'slot', 'id', 'count'}):
            raise DevelopmentError('malformed graphical reconnect inventory row')
        storage, slot = row.get('storage'), row.get('slot')
        if (type(storage) is not int or storage not in CONTAINERS
                or type(slot) is not int or not 0 <= slot <= 65535
                or (storage < 4 and slot >= 25) or (storage == 1000 and slot > 13)
                or key != f'{storage}:{slot}'
                or type(row.get('id')) is not int or not 0 < row['id'] < 2**32
                or type(row.get('count')) is not int or not 0 < row['count'] < 2**32):
            raise DevelopmentError('malformed graphical reconnect inventory row')
    return value


def require_sprint_receipt(value, entities):
    if (not isinstance(value, dict)
            or set(value) != {'requested', 'verified', 'scope', 'identities', 'request',
                              'tp_before', 'baselines', 'receipts'}
            or value.get('requested') is not True or value.get('verified') is not True
            or value.get('scope') != SPRINT_SCOPE):
        raise DevelopmentError('invalid graphical Sprint receipt')
    identities = value.get('identities')
    if not isinstance(identities, list) or len(identities) != 2:
        raise DevelopmentError('invalid graphical Sprint identities')
    for index, row in enumerate(identities):
        if (not isinstance(row, dict) or set(row) != {'name', 'entity_id', 'character_id'}
                or not isinstance(row.get('name'), str) or not 1 <= len(row['name']) <= 31
                or type(row.get('entity_id')) is not int or row['entity_id'] != entities[index]
                or type(row.get('character_id')) is not int
                or not 0 < row['character_id'] < 2**64):
            raise DevelopmentError('invalid graphical Sprint identities')
    if (identities[0]['name'] == identities[1]['name']
            or identities[0]['character_id'] == identities[1]['character_id']):
        raise DevelopmentError('graphical Sprint identities are not distinct')
    request, tp_before = value.get('request'), value.get('tp_before')
    if (type(request) is not int or not 1 <= request <= 65535
            or type(tp_before) is not int or not 50 <= tp_before <= 1000):
        raise DevelopmentError('invalid graphical Sprint request/readiness')
    baselines, receipts = value.get('baselines'), value.get('receipts')
    if (not isinstance(baselines, list) or len(baselines) != 2
            or not isinstance(receipts, list) or len(receipts) != 2):
        raise DevelopmentError('invalid graphical Sprint observations')
    mover = entities[0]
    expected_effect = {'source': mover, 'target': mover, 'action': 3, 'kind': 1,
        'request': request, 'result': 0, 'source_effects': [],
        'effects': [{'type': 18, 'value': 50, 'flag': 128, 'args': [0, 0, 30]}]}
    for index, (baseline, receipt) in enumerate(zip(baselines, receipts)):
        histories = baseline.get('histories') if isinstance(baseline, dict) else None
        if (not isinstance(baseline, dict) or set(baseline) != {'seq', 'histories'}
                or type(baseline.get('seq')) is not int or not 0 <= baseline['seq'] < 2**64
                or not isinstance(histories, dict) or set(histories) != set(SPRINT_HISTORIES)
                or any(not isinstance(rows, list) or len(rows) >= 128
                       or any(not isinstance(row, dict) for row in rows)
                       for rows in histories.values())
                or any(row.get('source') == mover and row.get('action') == 3
                       for key in ('effects', 'starts') for row in histories[key])):
            raise DevelopmentError('invalid graphical Sprint baseline')
        effect = receipt.get('effect') if isinstance(receipt, dict) else None
        if (not isinstance(receipt, dict)
                or set(receipt) != {'effect', 'zero_tp', 'start', 'received_seq'}
                or effect != expected_effect
                or any(type(effect.get(key)) is not int
                       for key in ('source', 'target', 'action', 'kind', 'request', 'result'))
                or any(type(item.get(key)) is not int for item in effect['effects']
                       for key in ('type', 'value', 'flag'))
                or any(type(arg) is not int for item in effect['effects'] for arg in item['args'])
                or type(receipt.get('received_seq')) is not int
                or not baseline['seq'] < receipt['received_seq'] < 2**64):
            raise DevelopmentError('invalid graphical Sprint received effect')
        hud = receipt.get('zero_tp')
        if (not isinstance(hud, dict)
                or set(hud) != {'target', 'hp', 'hp_max', 'mp', 'mp_max', 'tp'}
                or hud.get('target') != mover or hud.get('tp') != 0
                or any(type(hud.get(key)) is not int for key in ('target', 'hp', 'hp_max', 'mp', 'mp_max', 'tp'))
                or not 0 < hud['hp'] <= hud['hp_max']
                or not 0 <= hud['mp'] <= hud['mp_max']):
            raise DevelopmentError('invalid graphical Sprint zero-TP receipt')
        expected_start = ({'source': mover, 'action': 3, 'group': 56,
                           'recast_centiseconds': 3000} if index == 0 else None)
        if (receipt.get('start') != expected_start
                or (expected_start is not None
                    and any(type(value) is not int for value in receipt['start'].values()))):
            raise DevelopmentError('invalid graphical Sprint start metadata')
    if receipts[0]['effect'] != receipts[1]['effect']:
        raise DevelopmentError('graphical Sprint observers disagree')
    return value


def require_viewer_checkpoint(value, stage, expected_identity, run_id, observers, continuity=None):
    fields = {'verified', 'stage', 'identity', 'presence_tokens',
              'initial_observations', 'received_replies'}
    if continuity is not None:
        fields.add('continuous_presence')
    if (not isinstance(value, dict) or set(value) != fields
            or value.get('verified') is not True or value.get('stage') != stage
            or value.get('identity') != expected_identity
            or (stage == 'finish') != (continuity is not None)
            or (continuity is not None and value.get('continuous_presence') != continuity)):
        raise DevelopmentError('invalid graphical viewer checkpoint')
    tokens = value.get('presence_tokens')
    observations, replies = value.get('initial_observations'), value.get('received_replies')
    if (not isinstance(tokens, dict) or set(tokens) != set(observers)
            or any(type(tokens.get(observer)) is not int
                   or not 0 <= tokens[observer] < 2**64 for observer in observers)
            or not isinstance(observations, list) or len(observations) != 2
            or not isinstance(replies, list) or len(replies) != 2):
        raise DevelopmentError('invalid graphical viewer checkpoint observations')
    messages = []
    for observer, observation, reply in zip(observers, observations, replies):
        if (not isinstance(observation, dict)
                or set(observation) != {'entity_id', 'name', 'gm_rank', 'position', 'presence_token'}
                or {key: observation.get(key) for key in ('entity_id', 'name', 'gm_rank')} != expected_identity
                or type(observation.get('entity_id')) is not int
                or type(observation.get('gm_rank')) is not int
                or not position(observation.get('position'))
                or type(observation.get('presence_token')) is not int
                or observation['presence_token'] != tokens[observer]
                or not isinstance(reply, dict)
                or set(reply) != {'observer', 'viewer', 'message',
                                  'received_sequence', 'baseline_sequence'}
                or reply.get('observer') != observer
                or type(reply.get('baseline_sequence')) is not int
                or type(reply.get('received_sequence')) is not int
                or not tokens[observer] <= reply['baseline_sequence'] < reply['received_sequence'] < 2**64):
            raise DevelopmentError('invalid graphical viewer endpoint observation')
        viewer = reply.get('viewer')
        if (not isinstance(viewer, dict)
                or set(viewer) != {'entity_id', 'name', 'gm_rank', 'position', 'presence_token'}
                or {key: viewer.get(key) for key in ('entity_id', 'name', 'gm_rank')} != expected_identity
                or type(viewer.get('entity_id')) is not int or type(viewer.get('gm_rank')) is not int
                or not position(viewer.get('position'))
                or type(viewer.get('presence_token')) is not int
                or viewer['presence_token'] != tokens[observer]):
            raise DevelopmentError('invalid graphical viewer reply identity')
        message = reply.get('message')
        prefix = f'Sapphire viewer {run_id[:8]} {stage} '
        nonce = message[len(prefix):] if isinstance(message, str) and message.startswith(prefix) else ''
        if len(nonce) != 32 or any(char not in '0123456789abcdef' for char in nonce):
            raise DevelopmentError('graphical viewer reply is not a fresh run-bound challenge')
        messages.append(message)
    if messages[0] != messages[1]:
        raise DevelopmentError('graphical viewer reply was not received by both bots')
    return value


def require_movement_receipt(value, entities, cycles, waypoints, catalog_hash):
    fields = {'requested', 'verified', 'scope', 'cycles', 'authored_route',
              'mover_entity_id', 'witness_entity_id', 'speed',
              'baseline_witness_sequence', 'observations'}
    if (not isinstance(value, dict) or set(value) != fields
            or value.get('requested') is not True or value.get('verified') is not True
            or value.get('scope') != MOVEMENT_SCOPE
            or type(cycles) is not int or cycles != 1
            or type(value.get('cycles')) is not int or value['cycles'] != cycles
            or type(waypoints) is not int or not 2 <= waypoints <= 16
            or not isinstance(catalog_hash, str) or len(catalog_hash) != 64
            or any(char not in '0123456789abcdef' for char in catalog_hash)
            or value.get('mover_entity_id') != entities[0]
            or type(value.get('mover_entity_id')) is not int
            or value.get('witness_entity_id') != entities[1]
            or type(value.get('witness_entity_id')) is not int
            or type(value.get('speed')) is not float or value['speed'] != 2.0
            or type(value.get('baseline_witness_sequence')) is not int
            or not 0 <= value['baseline_witness_sequence'] < 2**64):
        raise DevelopmentError('invalid graphical movement receipt')
    route = value.get('authored_route')
    if (not isinstance(route, list) or len(route) != waypoints
            or any(not position(point) for point in route)
            or any(math.dist(left, right) <= 0 for left, right in zip(route, route[1:]))
            or sum(math.dist(left, right) for left, right in zip(route, route[1:])) > 5):
        raise DevelopmentError('invalid graphical authored movement route')
    plan = [*route[1:], *reversed(route[:-1])]
    observations = value.get('observations')
    if not isinstance(observations, list) or len(observations) != cycles * len(plan):
        raise DevelopmentError('incomplete graphical independent movement observations')
    prior = value['baseline_witness_sequence']
    for offset, observation in enumerate(observations):
        cycle, step = divmod(offset, len(plan))
        if (not isinstance(observation, dict)
                or set(observation) != {'cycle', 'step', 'target', 'received_position',
                                        'witness_sequence'}
                or type(observation.get('cycle')) is not int or observation['cycle'] != cycle
                or type(observation.get('step')) is not int or observation['step'] != step
                or observation.get('target') != plan[step]
                or not position(observation.get('target'))
                or not position(observation.get('received_position'))
                or math.dist(observation['target'], observation['received_position']) > 0.15
                or type(observation.get('witness_sequence')) is not int
                or not prior < observation['witness_sequence'] < 2**64):
            raise DevelopmentError('invalid graphical independent movement observation')
        prior = observation['witness_sequence']
    return value


def require_party_receipt(value, entities, run_id, territory):
    fields = {'requested', 'verified', 'scope', 'identities', 'party',
              'invitation_receipt', 'received_chat', 'both_empty_after_disband'}
    if (not isinstance(value, dict) or set(value) != fields
            or value.get('requested') is not True or value.get('verified') is not True
            or value.get('scope') != PARTY_SCOPE or value.get('both_empty_after_disband') is not True
            or not isinstance(value.get('identities'), list) or len(value['identities']) != 2):
        raise DevelopmentError('invalid graphical party receipt')
    identities = value['identities']
    for index, identity in enumerate(identities):
        if (not isinstance(identity, dict)
                or set(identity) != {'name', 'entity_id', 'character_id'}
                or not isinstance(identity.get('name'), str) or not 1 <= len(identity['name']) <= 31
                or type(identity.get('entity_id')) is not int or identity['entity_id'] != entities[index]
                or type(identity.get('character_id')) is not int
                or not 0 < identity['character_id'] < 2**64):
            raise DevelopmentError('invalid graphical party identity')
    if (identities[0]['name'] == identities[1]['name']
            or identities[0]['character_id'] == identities[1]['character_id']):
        raise DevelopmentError('graphical party identities are not distinct')
    party = value.get('party')
    if (not isinstance(party, dict)
            or set(party) != {'id', 'chat_channel', 'count', 'leader_index', 'members'}
            or type(party.get('id')) is not int or not 0 < party['id'] < 2**64
            or type(party.get('chat_channel')) is not int
            or not 0 < party['chat_channel'] < 2**64
            or type(party.get('count')) is not int or party['count'] != 2
            or type(party.get('leader_index')) is not int or party['leader_index'] != 0
            or not isinstance(party.get('members'), list) or len(party['members']) != 2):
        raise DevelopmentError('invalid graphical owned-party state')
    for identity, member in zip(identities, party['members']):
        if (not isinstance(member, dict)
                or set(member) != {'entity_id', 'character_id', 'name', 'territory',
                                   'class_job', 'level'}
                or any(type(member.get(key)) is not int for key in ('entity_id', 'character_id'))
                or {key: member.get(key) for key in ('entity_id', 'character_id', 'name')} != identity
                or type(member.get('territory')) is not int or member['territory'] != territory
                or type(member.get('class_job')) is not int or not 1 <= member['class_job'] <= 255
                or type(member.get('level')) is not int or not 1 <= member['level'] <= 100):
            raise DevelopmentError('invalid graphical owned-party member')
    invitation = value.get('invitation_receipt')
    if (not isinstance(invitation, dict) or set(invitation) != {'result', 'target'}
            or type(invitation.get('result')) is not int or invitation['result'] != 0
            or invitation.get('target') != identities[1]['name']):
        raise DevelopmentError('invalid graphical party invitation receipt')
    chats = value.get('received_chat')
    if not isinstance(chats, list) or len(chats) != 2:
        raise DevelopmentError('invalid graphical party chat receipts')
    for index, (identity, chat) in enumerate(zip(identities, chats)):
        if (not isinstance(chat, dict)
                or set(chat) != {'actor', 'channel', 'character_id', 'message',
                                 'name', 'party_id', 'token'}
                or any(type(chat.get(key)) is not int
                       for key in ('actor', 'channel', 'character_id', 'party_id', 'token'))
                or chat['actor'] != identity['entity_id']
                or chat['character_id'] != identity['character_id']
                or chat.get('name') != identity['name']
                or chat['party_id'] != party['id'] or chat['channel'] != party['chat_channel']
                or not 0 < chat['token'] < 2**64
                or chat.get('message') != f'Sapphire dev {run_id} party {index}'):
            raise DevelopmentError('invalid graphical party chat receipt')
    return value


def require_tell_receipt(value, entities, run_id):
    if (not isinstance(value, dict)
            or set(value) != {'requested', 'verified', 'scope', 'received_tells'}
            or value.get('requested') is not True or value.get('verified') is not True
            or value.get('scope') != TELL_SCOPE
            or not isinstance(value.get('received_tells'), list)
            or len(value['received_tells']) != 2):
        raise DevelopmentError('invalid graphical Tell receipt')
    rows = value['received_tells']
    for index, row in enumerate(rows):
        if (not isinstance(row, dict)
                or set(row) != {'sender', 'recipient', 'baseline_seq', 'received_seq', 'received'}):
            raise DevelopmentError('invalid graphical Tell observation')
        sender, recipient, received = row.get('sender'), row.get('recipient'), row.get('received')
        for identity, expected_entity in ((sender, entities[index]), (recipient, entities[1-index])):
            if (not isinstance(identity, dict)
                    or set(identity) != {'name', 'entity_id', 'character_id'}
                    or not isinstance(identity.get('name'), str)
                    or not 1 <= len(identity['name']) <= 31
                    or type(identity.get('entity_id')) is not int
                    or identity['entity_id'] != expected_entity
                    or type(identity.get('character_id')) is not int
                    or not 0 < identity['character_id'] < 2**64):
                raise DevelopmentError('invalid graphical Tell identity')
        baseline, sequence = row.get('baseline_seq'), row.get('received_seq')
        if (type(baseline) is not int or type(sequence) is not int
                or not 0 <= baseline < sequence < 2**64 or not isinstance(received, dict)
                or set(received) != {'actor', 'character_id', 'message', 'name', 'party_id', 'token'}
                or any(type(received.get(key)) is not int
                       for key in ('actor', 'character_id', 'party_id', 'token'))
                or received['actor'] != sender['entity_id']
                or received['character_id'] != sender['character_id']
                or received.get('name') != sender['name'] or received['party_id'] != 0
                or not baseline < received['token'] <= sequence):
            raise DevelopmentError('invalid graphical Tell received row')
        prefix = f'Sapphire dev {run_id} tell {index} '
        message = received.get('message')
        nonce = message[len(prefix):] if isinstance(message, str) and message.startswith(prefix) else ''
        if len(nonce) != 16 or any(char not in '0123456789abcdef' for char in nonce):
            raise DevelopmentError('graphical Tell challenge is not bound to this run')
    if (rows[0]['sender'] != rows[1]['recipient']
            or rows[0]['recipient'] != rows[1]['sender']
            or rows[0]['sender']['name'] == rows[0]['recipient']['name']
            or rows[0]['sender']['character_id'] == rows[0]['recipient']['character_id']):
        raise DevelopmentError('graphical Tell peers are not exact reciprocal identities')
    return value


def require_reconnect_receipt(value, identity, territory):
    fields = {'requested', 'verified', 'scope', 'identity_before', 'identity_after',
              'territory', 'expected_position', 'witness_before', 'received_after',
              'witness_after', 'old_server_close_observed', 'independent_despawn_observed',
              'post_login_say_observed', 'world_restart_performed'}
    if (not isinstance(value, dict) or set(value) != fields
            or value.get('requested') is not True or value.get('verified') is not True
            or value.get('scope') != 'fresh-login-position-not-world-restart'
            or value.get('identity_before') != identity or value.get('identity_after') != identity
            or any(not isinstance(value.get(side), dict)
                   or not isinstance(value[side].get('name'), str)
                   or type(value[side].get('entity_id')) is not int
                   or type(value[side].get('character_id')) is not int
                   for side in ('identity_before', 'identity_after'))
            or type(value.get('territory')) is not int or value['territory'] != territory
            or any(not position(value.get(key)) for key in
                   ('expected_position', 'witness_before', 'received_after', 'witness_after'))
            or any(math.dist(value['expected_position'], value[key]) > 0.15 for key in
                   ('witness_before', 'received_after', 'witness_after'))
            or value.get('old_server_close_observed') is not True
            or value.get('independent_despawn_observed') is not True
            or value.get('post_login_say_observed') is not True
            or value.get('world_restart_performed') is not False):
        raise DevelopmentError('invalid graphical equipment reconnect receipt')
    return value


def require_equipment_receipt(value, entities, territory, normal_inventory):
    fields = {'requested', 'verified', 'identity', 'scope', 'reconnects_required',
              'mutation_observation', 'before', 'class_job', 'unequip_expected',
              'unequip_publication_attempted', 'unequip_receipt', 'unequip_reconnect',
              'unequipped', 'before_reequip', 'reequip_publication_attempted',
              'reequip_receipt', 'reequip_reconnect', 'reequipped'}
    if (not isinstance(value, dict) or set(value) != fields
            or value.get('requested') is not True or value.get('verified') is not True
            or value.get('scope') != EQUIPMENT_SCOPE or value.get('reconnects_required') != 3
            or value.get('mutation_observation') != 'fresh-login-not-current-session-acknowledgement'
            or value.get('unequip_publication_attempted') is not True
            or value.get('reequip_publication_attempted') is not True):
        raise DevelopmentError('invalid graphical equipment receipt')
    identity = value.get('identity')
    if (not isinstance(identity, dict) or set(identity) != {'name', 'entity_id', 'character_id'}
            or not isinstance(identity.get('name'), str) or not 1 <= len(identity['name']) <= 31
            or type(identity.get('entity_id')) is not int or identity['entity_id'] != entities[0]
            or type(identity.get('character_id')) is not int
            or not 0 < identity['character_id'] < 2**64
            or type(value.get('class_job')) is not int or value['class_job'] not in {1, 2, 7}):
        raise DevelopmentError('invalid graphical equipment identity/class')
    before = require_inventory_projection(value.get('before'))
    unequipped = require_inventory_projection(value.get('unequipped'))
    before_reequip = require_inventory_projection(value.get('before_reequip'))
    reequipped = require_inventory_projection(value.get('reequipped'))
    before_rows = before['inventory']
    if before_rows.get('1000:3') != BODY or '0:0' in before_rows:
        raise DevelopmentError('graphical equipment starter-body precondition missing')
    expected = dict(before_rows)
    del expected['1000:3']
    expected['0:0'] = dict(BAG)
    if (value.get('unequip_expected') != expected
            or unequipped['inventory'] != expected or before_reequip['inventory'] != expected
            or normal_inventory['inventory'] != expected
            or reequipped['inventory'] != before_rows):
        raise DevelopmentError('graphical equipment fresh-login projections disagree')
    for key in ('unequip_receipt', 'reequip_receipt'):
        receipt = value.get(key)
        if (not isinstance(receipt, dict)
                or set(receipt) != {'context', 'operation', 'acknowledged', 'inventory_change_verified'}
                or type(receipt.get('context')) is not int or not 1 <= receipt['context'] < 2**32
                or type(receipt.get('operation')) is not int or receipt['operation'] != 8
                or receipt.get('acknowledged') is not True
                or receipt.get('inventory_change_verified') is not False):
            raise DevelopmentError('invalid graphical equipment publication receipt')
    require_reconnect_receipt(value.get('unequip_reconnect'), identity, territory)
    require_reconnect_receipt(value.get('reequip_reconnect'), identity, territory)
    return value


def require_decline_receipt(value, entities):
    fields = {'requested', 'verified', 'scope', 'identities', 'invitation_result',
              'received_reply', 'received_rejection', 'baseline_sequences',
              'received_sequences', 'both_empty_after_decline'}
    if (not isinstance(value, dict) or set(value) != fields
            or value.get('requested') is not True or value.get('verified') is not True
            or value.get('scope') != DECLINE_SCOPE
            or value.get('both_empty_after_decline') is not True
            or not isinstance(value.get('identities'), list) or len(value['identities']) != 2):
        raise DevelopmentError('invalid graphical party-decline receipt')
    identities = value['identities']
    for index, identity in enumerate(identities):
        if (not isinstance(identity, dict)
                or set(identity) != {'name', 'entity_id', 'character_id'}
                or not isinstance(identity.get('name'), str) or not 1 <= len(identity['name']) <= 31
                or type(identity.get('entity_id')) is not int or identity['entity_id'] != entities[index]
                or type(identity.get('character_id')) is not int
                or not 0 < identity['character_id'] < 2**64):
            raise DevelopmentError('invalid graphical party-decline identity')
    if (identities[0]['name'] == identities[1]['name']
            or identities[0]['character_id'] == identities[1]['character_id']):
        raise DevelopmentError('graphical party-decline identities are not distinct')
    invitation = value.get('invitation_result')
    reply, rejection = value.get('received_reply'), value.get('received_rejection')
    if (not isinstance(invitation, dict) or set(invitation) != {'result', 'target'}
            or type(invitation.get('result')) is not int or invitation['result'] != 0
            or invitation.get('target') != identities[1]['name']
            or reply != {'result': 0, 'auth_type': 1, 'answer': 0,
                         'name': identities[0]['name']}
            or not isinstance(reply, dict)
            or any(type(reply.get(key)) is not int for key in ('result', 'auth_type', 'answer'))
            or rejection != {'character_id': identities[1]['character_id'], 'auth_type': 1,
                             'result': 5, 'name': identities[1]['name']}
            or not isinstance(rejection, dict)
            or any(type(rejection.get(key)) is not int
                   for key in ('character_id', 'auth_type', 'result'))):
        raise DevelopmentError('invalid graphical party-decline outcome')
    baselines, received = value.get('baseline_sequences'), value.get('received_sequences')
    if (not isinstance(baselines, list) or not isinstance(received, list)
            or len(baselines) != 2 or len(received) != 2
            or any(type(sequence) is not int for sequence in [*baselines, *received])
            or any(not 0 <= baseline < sequence < 2**64
                   for baseline, sequence in zip(baselines, received))):
        raise DevelopmentError('invalid graphical party-decline sequence evidence')
    return value


def require_graphical_viewer_receipt(viewer, viewer_name, entity, entities, run_id, finish_mover):
    expected = {'entity_id':entity, 'name':viewer_name, 'gm_rank':0}
    if (not isinstance(viewer, dict)
            or set(viewer) != {'requested', 'verified', 'scope', 'viewer_login_or_control_performed',
                               'start', 'finish', 'continuous_presence'}
            or viewer.get('requested') is not True or viewer.get('verified') is not True
            or viewer.get('scope') != VIEWER_SCOPE
            or viewer.get('viewer_login_or_control_performed') is not False):
        raise DevelopmentError('runner must retain exact no-control graphical viewer evidence')
    continuity = viewer.get('continuous_presence')
    if (not isinstance(continuity, dict)
            or set(continuity) != {'verified', 'scope', 'observer', 'observer_entity_id',
                                   'viewer_entity_id', 'presence_token'}
            or continuity.get('verified') is not True
            or continuity.get('scope') != CONTINUITY_SCOPE
            or continuity.get('observer') != 'witness'
            or continuity.get('observer_entity_id') != entities[1]
            or continuity.get('viewer_entity_id') != entity
            or type(continuity.get('presence_token')) is not int
            or continuity['presence_token'] < 0
            or not isinstance(viewer.get('finish'), dict)
            or viewer['finish'].get('continuous_presence') != continuity):
        raise DevelopmentError('continuous received graphical-viewer presence evidence missing or changed')
    require_viewer_checkpoint(
        viewer.get('start'), 'start', expected, run_id, ('mover', 'witness'))
    require_viewer_checkpoint(
        viewer.get('finish'), 'finish', expected, run_id, (finish_mover, 'witness'), continuity)
    return expected, continuity


def require_shared_runner_metadata(result, *, catalog_required):
    worker_hash, catalog_hash = result.get('worker_sha256'), result.get('catalog_sha256')
    if (type(result.get('version')) is not int or result['version'] != 1
            or result.get('protocol') != 'sapphire-3.3'
            or type(result.get('cycles')) is not int or result['cycles'] != 1
            or result.get('server_identity_verified') is not False
            or result.get('server_processes_owned') is not False
            or result.get('database_access') is not False
            or result.get('account_reset_performed_by_runner') is not False
            or result.get('administrative_preparation_wait_enabled') is not False
            or result.get('administrative_command_execution_attested') is not False
            or result.get('world_restart_performed') is not False
            or not isinstance(worker_hash, str) or len(worker_hash) != 64
            or any(char not in '0123456789abcdef' for char in worker_hash)
            or (catalog_required and (not isinstance(catalog_hash, str)
                                      or len(catalog_hash) != 64
                                      or any(char not in '0123456789abcdef' for char in catalog_hash)))
            or (not catalog_required and catalog_hash is not None)):
        raise DevelopmentError('graphical bot run metadata does not retain shared-runner boundaries')
    return worker_hash


def require_graphical_run_pair(comprehensive, decline, expected_names, expected_worker_sha256):
    """Bind two strict results to the same dedicated characters, not session exclusion."""
    if (not isinstance(expected_names, list) or len(expected_names) != 2
            or any(not isinstance(name, str) or not 1 <= len(name) <= 31
                   for name in expected_names)
            or len(set(expected_names)) != 2
            or not isinstance(expected_worker_sha256, str)
            or len(expected_worker_sha256) != 64
            or any(char not in '0123456789abcdef' for char in expected_worker_sha256)):
        raise DevelopmentError('invalid expected graphical bot-run provenance')
    main_run, decline_run = comprehensive.get('run_id'), decline.get('run_id')
    main_entities, decline_entities = comprehensive.get('entities'), decline.get('entities')
    main_identities = comprehensive.get('sprint_verification', {}).get('identities')
    decline_identities = decline.get('decline_verification', {}).get('identities')
    if (not isinstance(main_run, str) or len(main_run) != 32
            or not isinstance(decline_run, str) or len(decline_run) != 32
            or main_run == decline_run
            or any(char not in '0123456789abcdef' for char in main_run + decline_run)
            or comprehensive.get('worker_sha256') != expected_worker_sha256
            or decline.get('worker_sha256') != expected_worker_sha256
            or not isinstance(main_entities, list) or len(main_entities) != 2
            or main_entities != decline_entities or len(set(main_entities)) != 2
            or any(type(value) is not int or value <= 0 for value in main_entities)
            or not isinstance(main_identities, list) or main_identities != decline_identities
            or len(main_identities) != 2
            or any(not isinstance(identity, dict)
                   or set(identity) != {'name', 'entity_id', 'character_id'}
                   or type(identity.get('entity_id')) is not int
                   or type(identity.get('character_id')) is not int
                   or not 0 < identity['character_id'] < 2**64
                   for identity in main_identities)
            or len({identity['character_id'] for identity in main_identities}) != 2
            or [identity['name'] for identity in main_identities] != expected_names
            or [identity['entity_id'] for identity in main_identities] != main_entities):
        raise DevelopmentError('graphical bot runs do not share exact dedicated-character provenance')
    # The individual strict consumers additionally validate each lifecycle receipt.
    return {'verified': True,
            'scope': 'same-dedicated-bot-identities-across-distinct-runs-not-offline-or-reset-proof',
            'comprehensive_run_id': main_run, 'decline_run_id': decline_run,
            'worker_sha256': expected_worker_sha256,
            'identities': main_identities}


def require_graphical_witness_handoff(initial_state, retirement, run_pair, expected_name):
    """Join the original observer's identity/closure to the paired mover identity."""
    identities = run_pair.get('identities') if isinstance(run_pair, dict) else None
    if (not isinstance(identities, list) or len(identities) != 2
            or run_pair.get('verified') is not True
            or run_pair.get('scope') !=
                'same-dedicated-bot-identities-across-distinct-runs-not-offline-or-reset-proof'
            or not isinstance(expected_name, str) or not expected_name
            or not isinstance(initial_state, dict)
            or initial_state.get('phase') != 'ready' or initial_state.get('territory') != 130
            or initial_state.get('gm_rank') != 0 or initial_state.get('party') != EMPTY_PARTY
            or initial_state.get('pending_party_invite') is not None
            or not isinstance(retirement, dict)
            or set(retirement) != {'bot', 'server_close_observed', 'native_bot_removed', 'scope'}
            or retirement.get('bot') != 'witness'
            or retirement.get('server_close_observed') is not True
            or retirement.get('native_bot_removed') is not True
            or retirement.get('scope') !=
                'normal-witness-session-retirement-not-offline-exclusion'):
        raise DevelopmentError('graphical witness handoff lacks exact identity/closure provenance')
    identity = received_character_identity(initial_state, expected_name)
    if identity != identities[0] or initial_state.get('entity_id') != identity['entity_id']:
        raise DevelopmentError('original graphical witness differs from paired mover')
    return {'verified': True,
            'scope': 'same-dedicated-witness-across-normal-handoff-not-offline-exclusion',
            'identity': identity, 'retirement_scope': retirement['scope'],
            'comprehensive_run_id': run_pair['comprehensive_run_id'],
            'decline_run_id': run_pair['decline_run_id']}


def require_graphical_logout_witness(state, run_pair, viewer_name, viewer_entity):
    """Bind the fresh final observer to the paired mover and received viewer."""
    fields = {'verified', 'scope', 'comprehensive_run_id', 'decline_run_id',
              'worker_sha256', 'identities'}
    identities = run_pair.get('identities') if isinstance(run_pair, dict) else None
    if (not isinstance(run_pair, dict) or set(run_pair) != fields
            or run_pair.get('verified') is not True
            or run_pair.get('scope') !=
                'same-dedicated-bot-identities-across-distinct-runs-not-offline-or-reset-proof'
            or not isinstance(identities, list) or len(identities) != 2
            or any(not isinstance(row, dict)
                   or set(row) != {'name', 'entity_id', 'character_id'}
                   or not isinstance(row.get('name'), str) or not 1 <= len(row['name']) <= 31
                   or type(row.get('entity_id')) is not int or row['entity_id'] <= 0
                   or type(row.get('character_id')) is not int
                   or not 0 < row['character_id'] < 2**64 for row in identities)
            or len({row['name'] for row in identities}) != 2
            or len({row['entity_id'] for row in identities}) != 2
            or len({row['character_id'] for row in identities}) != 2
            or any(not isinstance(run_pair.get(key), str)
                   or len(run_pair[key]) != 32
                   or any(char not in '0123456789abcdef' for char in run_pair[key])
                   for key in ('comprehensive_run_id', 'decline_run_id'))
            or run_pair['comprehensive_run_id'] == run_pair['decline_run_id']
            or not isinstance(run_pair.get('worker_sha256'), str)
            or len(run_pair['worker_sha256']) != 64
            or any(char not in '0123456789abcdef' for char in run_pair['worker_sha256'])):
        raise DevelopmentError('final graphical witness requires exact paired-run provenance')
    expected = identities[0]
    if (not idle_state(state, 130) or state.get('entity_id') != expected.get('entity_id')
            or state.get('party') != EMPTY_PARTY
            or state.get('pending_party_invite') is not None):
        raise DevelopmentError('final graphical witness is not an idle ungrouped paired mover')
    identity = received_character_identity(state, expected.get('name'))
    if identity != expected:
        raise DevelopmentError('final graphical witness character differs from paired mover')
    viewer = observe_viewer(state, viewer_name, 130, identity['entity_id'],
                            [row['entity_id'] for row in identities])
    if (viewer is None or viewer['entity_id'] != viewer_entity or viewer['gm_rank'] != 0):
        raise DevelopmentError('final graphical witness lacks exact received non-GM viewer')
    return {'verified': True,
            'scope': 'fresh-paired-witness-login-and-viewer-presence-not-offline-exclusion',
            'identity': identity, 'viewer': viewer, 'received_sequence': state['seq']}


def require_graphical_decline_check(result, viewer_name, entity):
    """Require a separate fresh-session decline; never conflate it with party creation."""
    if (result.get('status') != 'passed' or result.get('scope') != 'shared-development-not-acceptance'
            or result.get('lease_retained') is not False or result.get('worker_closed') is not True
            or result.get('administrative_preparation_wait_enabled') is not False
            or result.get('database_access') is not False or result.get('world_restart_performed') is not False
            or result.get('movement_waypoints_per_cycle') != 0
            or result.get('movement_verification') != {'requested': False, 'verified': False}):
        raise DevelopmentError('graphical decline run did not complete cleanly')
    require_shared_runner_metadata(result, catalog_required=False)
    require_clear_terminal_account_leases(result)
    require_normal_worker_exit(result)
    deadline = result.get('run_deadline')
    if (not isinstance(deadline, dict)
            or set(deadline) != {'enabled', 'limit_seconds', 'expired',
                                 'session_work_completed_within_budget', 'scope',
                                 'cleanup_may_exceed_deadline'}
            or deadline.get('enabled') is not True
            or type(deadline.get('limit_seconds')) is not int
            or not 1 <= deadline['limit_seconds'] <= 900
            or deadline.get('expired') is not False
            or deadline.get('session_work_completed_within_budget') is not True
            or deadline.get('scope') != 'cooperative-success-deadline-not-hard-process-limit'
            or deadline.get('cleanup_may_exceed_deadline') is not True):
        raise DevelopmentError('bounded graphical decline receipt missing or failed')
    entities, territory, run_id = result.get('entities'), result.get('territory'), result.get('run_id')
    if (not isinstance(entities, list) or len(entities) != 2
            or any(type(value) is not int or value <= 0 for value in entities)
            or len(set(entities)) != 2 or type(territory) is not int or territory != 130
            or not isinstance(run_id, str) or len(run_id) != 32
            or any(char not in '0123456789abcdef' for char in run_id)):
        raise DevelopmentError('graphical decline entities/territory missing or invalid')
    for key in ('reconnect_verification', 'inventory_verification', 'party_verification',
                'tell_verification', 'sprint_verification', 'equipment_verification'):
        if result.get(key) != {'requested': False, 'verified': False}:
            raise DevelopmentError('graphical decline run included a foreign subscenario')
    decline = require_decline_receipt(result.get('decline_verification'), entities)
    expected, continuity = require_graphical_viewer_receipt(
        result.get('viewer_verification'), viewer_name, entity, entities, run_id, 'mover')
    return {'status':'passed', 'scope':'graphical-fixture-with-separate-fresh-party-decline',
            'viewer':expected, 'run_deadline':deadline, 'decline_scope':decline['scope'],
            'continuous_presence':continuity, 'rendered_bot_actions_verified':False,
            'note':'Received decline/viewer evidence is not general social or rendered-action proof.'}


def require_graphical_check(result, viewer_name, entity):
    """No acknowledgement-only or foreign-viewer result can close this bridge."""
    if (result.get('status') != 'passed' or result.get('scope') != 'shared-development-not-acceptance'
            or result.get('lease_retained') is not False or result.get('worker_closed') is not True
            or result.get('administrative_preparation_wait_enabled') is not False
            or result.get('database_access') is not False or result.get('world_restart_performed') is not False
            or result.get('movement_waypoints_per_cycle', 0) < 2):
        raise DevelopmentError('normal development check did not complete cleanly')
    require_shared_runner_metadata(result, catalog_required=True)
    require_clear_terminal_account_leases(result)
    require_normal_worker_exit(result)
    deadline = result.get('run_deadline')
    if (not isinstance(deadline, dict)
            or set(deadline) != {'enabled', 'limit_seconds', 'expired',
                                 'session_work_completed_within_budget', 'scope',
                                 'cleanup_may_exceed_deadline'}
            or deadline.get('enabled') is not True
            or type(deadline.get('limit_seconds')) is not int
            or not 1 <= deadline['limit_seconds'] <= 900
            or deadline.get('expired') is not False
            or deadline.get('session_work_completed_within_budget') is not True
            or deadline.get('scope') != 'cooperative-success-deadline-not-hard-process-limit'
            or deadline.get('cleanup_may_exceed_deadline') is not True):
        raise DevelopmentError('bounded development run receipt missing or failed')
    entities, territory, run_id = result.get('entities'), result.get('territory'), result.get('run_id')
    if (not isinstance(entities, list) or len(entities) != 2
            or any(type(value) is not int or value <= 0 for value in entities)
            or len(set(entities)) != 2 or type(territory) is not int or territory != 130
            or not isinstance(run_id, str) or len(run_id) != 32
            or any(char not in '0123456789abcdef' for char in run_id)):
        raise DevelopmentError('normal development entities/territory missing or invalid')
    for key in ('movement_verification', 'party_verification', 'tell_verification',
                'reconnect_verification', 'inventory_verification', 'sprint_verification',
                'equipment_verification', 'viewer_verification'):
        value = result.get(key, {})
        if (not isinstance(value, dict) or value.get('requested') is not True
                or value.get('verified') is not True):
            raise DevelopmentError('required development subcheck missing or failed')
    if result.get('decline_verification') != {'requested': False, 'verified': False}:
        raise DevelopmentError('party creation and decline must remain separate fresh runs')
    movement = require_movement_receipt(
        result['movement_verification'], entities, result.get('cycles'),
        result.get('movement_waypoints_per_cycle'), result.get('catalog_sha256'))
    inventory = result['inventory_verification']
    if (set(inventory) != {'requested', 'verified', 'scope', 'before', 'after', 'changed_slots'}
            or inventory.get('scope') != INVENTORY_SCOPE or inventory.get('changed_slots') != []):
        raise DevelopmentError('invalid graphical reconnect inventory receipt')
    before = require_inventory_projection(inventory.get('before'))
    after = require_inventory_projection(inventory.get('after'))
    if before['inventory'] != after['inventory']:
        raise DevelopmentError('graphical reconnect inventory projection changed')
    party = require_party_receipt(result['party_verification'], entities, run_id, territory)
    tell = require_tell_receipt(result['tell_verification'], entities, run_id)
    sprint = require_sprint_receipt(result['sprint_verification'], entities)
    equipment = require_equipment_receipt(
        result['equipment_verification'], entities, territory, before)
    reconnect = require_reconnect_receipt(
        result['reconnect_verification'], equipment['identity'], territory)
    if math.dist(movement['authored_route'][0], reconnect['expected_position']) > 0.15:
        raise DevelopmentError('graphical movement and reconnect origins disagree')
    expected, continuity = require_graphical_viewer_receipt(
        result['viewer_verification'], viewer_name, entity, entities, run_id,
        'mover-equipment-reequipped')
    return {'status':'passed', 'scope':'graphical-fixture-checkpoints-with-normal-bot-scenario',
            'viewer':expected, 'run_deadline':deadline,
            'movement_scope':movement['scope'], 'inventory_scope':INVENTORY_SCOPE,
            'reconnect_scope':reconnect['scope'],
            'party_scope':party['scope'], 'tell_scope':tell['scope'],
            'sprint_scope':sprint['scope'],
            'equipment_scope':equipment['scope'], 'continuous_presence':continuity,
            'rendered_bot_actions_verified':False,
            'note':'Persistent-witness continuity and bot Sprint/equipment receipts are received-state evidence, not server-session or rendered-action agreement.'}
