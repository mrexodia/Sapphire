"""Bridge the owned manual graphical fixture to the separate normal-bot lane."""
import math
import time

from .development import (DevelopmentError, validate_profile, movement_route,
                          require_normal_worker_exit)
from .worker import Worker, WorkerError
from .development_lease import require_clear_terminal_account_leases
from .development_inventory import CONTAINERS, SCOPE as INVENTORY_SCOPE
from .development_viewer import CONTINUITY_SCOPE


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
                  verify_reconnect=True, verify_inventory=True, viewer_name=viewer_name,
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


def require_graphical_check(result, viewer_name, entity):
    """No acknowledgement-only or foreign-viewer result can close this bridge."""
    if (result.get('status') != 'passed' or result.get('scope') != 'shared-development-not-acceptance'
            or result.get('lease_retained') is not False or result.get('worker_closed') is not True
            or result.get('administrative_preparation_wait_enabled') is not False
            or result.get('database_access') is not False or result.get('world_restart_performed') is not False
            or result.get('movement_waypoints_per_cycle', 0) < 2):
        raise DevelopmentError('normal development check did not complete cleanly')
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
    for key in ('party_verification', 'tell_verification', 'reconnect_verification',
                'inventory_verification', 'viewer_verification'):
        value = result.get(key, {})
        if (not isinstance(value, dict) or value.get('requested') is not True
                or value.get('verified') is not True):
            raise DevelopmentError('required development subcheck missing or failed')
    inventory = result['inventory_verification']
    if (set(inventory) != {'requested', 'verified', 'scope', 'before', 'after', 'changed_slots'}
            or inventory.get('scope') != INVENTORY_SCOPE or inventory.get('changed_slots') != []):
        raise DevelopmentError('invalid graphical reconnect inventory receipt')
    before = require_inventory_projection(inventory.get('before'))
    after = require_inventory_projection(inventory.get('after'))
    if before['inventory'] != after['inventory']:
        raise DevelopmentError('graphical reconnect inventory projection changed')
    viewer = result['viewer_verification']
    if viewer.get('viewer_login_or_control_performed') is not False:
        raise DevelopmentError('runner must not control the graphical viewer')
    expected = {'entity_id':entity, 'name':viewer_name, 'gm_rank':0}
    if any(viewer.get(stage, {}).get('identity') != expected for stage in ('start','finish')):
        raise DevelopmentError('development checkpoints do not bind the same graphical fixture')
    entities = result.get('entities')
    continuity = viewer.get('continuous_presence')
    if (not isinstance(entities, list) or len(entities) != 2
            or any(type(value) is not int or value <= 0 for value in entities)
            or len(set(entities)) != 2 or not isinstance(continuity, dict)
            or set(continuity) != {'verified', 'scope', 'observer', 'observer_entity_id',
                                   'viewer_entity_id', 'presence_token'}
            or continuity.get('verified') is not True
            or continuity.get('scope') != CONTINUITY_SCOPE
            or continuity.get('observer') != 'witness'
            or continuity.get('observer_entity_id') != entities[1]
            or continuity.get('viewer_entity_id') != entity
            or type(continuity.get('presence_token')) is not int
            or continuity['presence_token'] < 0
            or viewer.get('finish', {}).get('continuous_presence') != continuity):
        raise DevelopmentError('continuous received graphical-viewer presence evidence missing or changed')
    return {'status':'passed', 'scope':'graphical-fixture-checkpoints-with-normal-bot-scenario',
            'viewer':expected, 'run_deadline':deadline,
            'inventory_scope':INVENTORY_SCOPE, 'continuous_presence':continuity,
            'rendered_bot_actions_verified':False,
            'note':'Endpoint replies are received-state evidence, not continuous presence or rendered-action agreement.'}
