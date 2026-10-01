"""Administrative request contracts; never gameplay/mutation proof."""
import copy
import json
from types import SimpleNamespace

import pytest

from .support.development import DevelopmentError
from .support.development_operator import request_registered_placement


class OperatorWorker:
    def __init__(self, artifacts):
        self.artifacts = artifacts
        self.requests = []
        self.supported = True
        self.fail = False
        self.identity = {"name": "Tester Operator", "entity_id": 3, "character_id": 300}
        self.state = {"phase": "ready", "territory": 130, "entity_id": 3, "gm_rank": 1,
                      "moving": False, "between_areas": False, "event_id": None, "scene": None,
                      "party": {"count": 0, "id": 0}, "pending_party_invite": None,
                      "characters": [self.identity]}

    def snapshot(self, name): return copy.deepcopy(self.state)

    def request(self, method, bot=None, **args):
        if method == "capabilities":
            return {"methods": ["development_place_registered"] if self.supported else []}
        assert method == "development_place_registered"
        self.requests.append(args)
        path = self.artifacts / f"placement-request-{args['approval_id']}-{args['slot']}.json"
        intent = json.loads(path.read_text())
        assert intent["status"] == "publication_outcome_unknown" and not intent["placement_verified"]
        if self.fail: raise TimeoutError("uncertain publication")
        return {"scope": "administrative-preparation-not-gameplay", "publication": "local-only", "placement_verified": False}


@pytest.fixture
def registry():
    return {"version": 1, "purpose": "development-bot-placement", "approval_id": "a" * 32, "territory": 130,
            "bots": [{"name": "Tester " + "A" * 12, "entity_id": 1, "character_id": 100},
                     {"name": "Tester " + "B" * 12, "entity_id": 2, "character_id": 200}]}


def invoke(worker, registry, path, **kwargs):
    return request_registered_placement(worker, SimpleNamespace(name="operator"), "Tester Operator",
                                        registry, kwargs.pop("slot", 0), path, **kwargs)


def test_explicit_setup_and_local_only_receipt(tmp_path, registry):
    worker = OperatorWorker(tmp_path)
    with pytest.raises(DevelopmentError): invoke(worker, registry, tmp_path)
    assert not worker.requests and not list(tmp_path.iterdir())
    result = invoke(worker, registry, tmp_path, approved=True)
    assert not result["placement_verified"] and result["status"] == "local_publication_only"
    assert worker.requests[0]["expected_operator"] == worker.identity
    assert worker.requests[0]["administrative_setup"] is True
    with pytest.raises(FileExistsError): invoke(worker, registry, tmp_path, approved=True)
    assert len(worker.requests) == 1


def test_uncertain_dispatch_keeps_intent_and_never_retries(tmp_path, registry):
    worker = OperatorWorker(tmp_path); worker.fail = True
    with pytest.raises(TimeoutError): invoke(worker, registry, tmp_path, approved=True)
    with pytest.raises(FileExistsError): invoke(worker, registry, tmp_path, approved=True)
    assert len(worker.requests) == 1
    assert json.loads(next(tmp_path.glob("*.json")).read_text())["status"] == "publication_outcome_unknown"


@pytest.mark.parametrize("field,value", [("gm_rank", 0), ("gm_rank", True), ("gm_rank", 256),
    ("phase", "loading"), ("moving", True), ("between_areas", True), ("scene", {}),
    ("event_id", 1), ("territory", 182), ("party", {"id": 3, "count": 2}),
    ("pending_party_invite", {}), ("entity_id", 4), ("characters", [])])
def test_non_gm_or_changed_operator_state_never_dispatches(tmp_path, registry, field, value):
    worker = OperatorWorker(tmp_path); worker.state[field] = value
    with pytest.raises(DevelopmentError): invoke(worker, registry, tmp_path, approved=True)
    assert not worker.requests and not list(tmp_path.iterdir())


def test_old_worker_and_self_target_rejected(tmp_path, registry):
    worker = OperatorWorker(tmp_path); worker.supported = False
    with pytest.raises(DevelopmentError): invoke(worker, registry, tmp_path, approved=True)
    worker.supported = True
    registry["bots"][0]["character_id"] = 300
    with pytest.raises(DevelopmentError): invoke(worker, registry, tmp_path, approved=True)
    assert not worker.requests


@pytest.mark.parametrize("slot", [True, -1, 2, "0"])
def test_only_two_integer_slots(tmp_path, registry, slot):
    worker = OperatorWorker(tmp_path)
    with pytest.raises(DevelopmentError): invoke(worker, registry, tmp_path, approved=True, slot=slot)
    assert not worker.requests
