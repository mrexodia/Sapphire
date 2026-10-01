"""Bridge the owned manual graphical fixture to the separate normal-bot lane."""
import time

from .development import (DevelopmentError, validate_profile, movement_route,
                          require_normal_worker_exit)
from .worker import Worker, WorkerError


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


def require_graphical_check(result, viewer_name, entity):
    """No acknowledgement-only or foreign-viewer result can close this bridge."""
    if (result.get('status') != 'passed' or result.get('scope') != 'shared-development-not-acceptance'
            or result.get('lease_retained') is not False or result.get('worker_closed') is not True
            or result.get('administrative_preparation_wait_enabled') is not False
            or result.get('database_access') is not False or result.get('world_restart_performed') is not False
            or result.get('movement_waypoints_per_cycle', 0) < 2):
        raise DevelopmentError('normal development check did not complete cleanly')
    require_normal_worker_exit(result)
    for key in ('party_verification', 'tell_verification', 'reconnect_verification', 'viewer_verification'):
        value = result.get(key, {})
        if value.get('requested') is not True or value.get('verified') is not True:
            raise DevelopmentError('required development subcheck missing or failed')
    viewer = result['viewer_verification']
    if viewer.get('viewer_login_or_control_performed') is not False:
        raise DevelopmentError('runner must not control the graphical viewer')
    expected = {'entity_id':entity, 'name':viewer_name, 'gm_rank':0}
    if any(viewer.get(stage, {}).get('identity') != expected for stage in ('start','finish')):
        raise DevelopmentError('development checkpoints do not bind the same graphical fixture')
    return {'status':'passed', 'scope':'graphical-fixture-checkpoints-with-normal-bot-scenario',
            'viewer':expected, 'rendered_bot_actions_verified':False,
            'note':'Endpoint replies are received-state evidence, not continuous presence or rendered-action agreement.'}
