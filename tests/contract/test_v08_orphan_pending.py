"""v0.8 D2''''': the held-state check must not dead-end on a binding drift.

What v0.8 RQ21 measured on five archived episodes (all identical in shape): at the round the
object was picked, the pending set **did** name it by entity id; one round later the row's
`entity_id` had fallen back to the declared attribute pair -- because that frame did not resolve
the declaration (#26 intermittency, or #25 for the two-yellow pair) -- and `pending_assignments`
then **dropped the row** because `world.has_entity("<attribute dict>")` is false. The rule policy
then held an object no pending goal named, and closed the episode as blocked.

Five properties are pinned here, and the first two are the red ones on the pre-fix code:

1. **an unbound-but-pending row stays pending for the decision** -- it is a real obligation whose
   binding could not be measured, not a finished one;
2. **the held check matches such a row by attributes**, so the policy places rather than blocks;
3. **the dead end is still detected**: a held object that no pending row names, even by
   attributes, is still blocked, with the reason string unchanged;
4. **the id-keyed path does not move** (no behaviour drift for the privileged channel);
5. **the one-shot plan path still plans only resolvable steps** -- a row keyed by attributes must
   not become a `pick(object_id="{...}")` step, so the unbound rows are opt-in for the decision
   seam only.

No test here spends a request or needs a camera: the drift is injected at the verifier seam,
which is where the camera channel produces it.
"""
from __future__ import annotations

import ast

import pytest

from embodied_agent.core.contracts import DecisionContext, GoalSpec, TaskInput
from embodied_agent.core.planner import RulePlanner
from embodied_agent.core.verify import RuntimeVerifier
from agent_lab.evaluation.run import task_input
from agent_lab.evaluation.tasks import find_case

CASE = "smoke_clean"
GREEN = {"color": "green", "shape": "cube"}


class _DriftedProgress:
    """Progress in the shape the camera channel produces when a declaration will not bind.

    The production row for an unbound assignment carries the declared attributes **as its
    `entity_id`** (a literal dict string) and `value="unknown"` with `entity_binding` among its
    unmeasured list -- that is exactly what the five archived episodes show. Stubbing the
    verifier's `progress` is the honest way to reproduce it: constructing a world that refuses to
    bind an attribute it can see would test a fiction instead.

    It is a class rather than a lambda because `monkeypatch.setattr` puts it on the class, where
    `RuntimeVerifier(world, ...)` then hands it a `self` it does not use.
    """

    rows: list = []

    def __init__(self, world=None, config=None, *, source=None, gmap=None):
        pass

    def __iter__(self):
        # `pending_assignments` iterates `v.progress(goal)`'s **result**, and the patched class
        # is what that call returns -- so the class itself has to be the row sequence.
        return iter(self.rows)

    def progress(self, goal, world):
        return list(self.rows)


def _item(entity_id, target_id, value="unknown"):
    class _Row:
        pass

    row = _Row()
    row.entity_id = entity_id
    row.target_id = target_id
    row.value = value
    return row


@pytest.fixture()
def held_world(world_for):
    """A real measured world whose first object is in the gripper.

    The world is re-measured after the skill runs (the same thing the production loop's
    `world_provider` does), because `held_object` is a property of the snapshot and a cached
    snapshot would report an empty hand after a completed grasp -- which would make the held
    check untestable for the wrong reason.
    """
    from embodied_agent.core.contracts import SkillCall
    from embodied_agent.core.placement_planner import PlacementPlanner
    from embodied_agent.core.runtime import build_world_state
    from embodied_agent.core.skills import SkillExecutor

    case = find_case(CASE)
    scene, _initial = world_for(CASE)
    version = {"n": 1}

    def snapshot():
        version["n"] += 1
        return build_world_state(scene, version["n"], f"obs_{version['n']:04d}", case.verify)

    executor = SkillExecutor(scene, world_provider=snapshot, config=case.verify,
                             planner=PlacementPlanner(scene, case.verify))
    entity = snapshot().entities[0]
    result = executor.execute(SkillCall(call_id="c_probe", plan_id="p_probe", step_id="s0",
                                        skill="pick", args={"object_id": entity.entity_id}))
    assert result.status == "completed", result.status
    world = snapshot()
    assert world.held_object == entity.entity_id, (world.held_object, entity.entity_id)
    return case, world, entity


def _context(case, world, goal):
    task = task_input(case)
    return DecisionContext(episode_id="v08-unit", state_version=world.state_version, task=task,
                           goal=goal, world=world, observation_ref=world.observation_ref)


def _goal_with(entity_ref_attributes, target_id):
    from embodied_agent.core.contracts import EntityRef, GoalAssignment

    return GoalSpec(goal_id="g_unit",
                    assignments=[GoalAssignment(entity=EntityRef(attributes=entity_ref_attributes),
                                                target_id=target_id)])


def test_an_unbound_row_stays_pending_for_the_decision(monkeypatch, held_world):
    """Red on the pre-fix code: the row is dropped, so `decide` cannot see the obligation."""
    case, world, entity = held_world
    drifted = _declared_key(entity)
    _DriftedProgress.rows = [_item(drifted, "tray_left")]
    monkeypatch.setattr(RuntimeVerifier, "progress", _DriftedProgress)
    planner = RulePlanner(case.verify)
    goal = _goal_with(dict(entity.attributes), "tray_left")

    with_unbound = planner.pending_assignments(goal, world, include_unbound=True)
    assert [row[0] for row in with_unbound] == [drifted], with_unbound
    # the plan path keeps its old, resolvable-only reading
    assert planner.pending_assignments(goal, world) == [], "mode A must not plan unbound rows"


def test_the_held_check_matches_an_unbound_row_by_attributes(monkeypatch, held_world):
    """Red on the pre-fix code: the decision comes back `blocked`."""
    case, world, entity = held_world
    drifted = _declared_key(entity)
    _DriftedProgress.rows = [_item(drifted, "tray_right")]
    monkeypatch.setattr(RuntimeVerifier, "progress", _DriftedProgress)
    planner = RulePlanner(case.verify)
    goal = _goal_with(dict(entity.attributes), "tray_right")

    decision = planner.decide(_context(case, world, goal))
    assert decision.action == "execute", decision.rationale
    assert decision.execute.skill == "place"
    assert decision.execute.args["object_id"] == entity.entity_id
    assert decision.execute.args["target_id"] == "tray_right"


def test_a_held_object_no_pending_row_names_is_still_blocked(monkeypatch, held_world):
    case, world, entity = held_world
    _DriftedProgress.rows = [_item("{'color': 'purple', 'shape': 'cube'}", "tray_left")]
    monkeypatch.setattr(RuntimeVerifier, "progress", _DriftedProgress)
    planner = RulePlanner(case.verify)
    goal = _goal_with({"color": "purple", "shape": "cube"}, "tray_left")

    decision = planner.decide(_context(case, world, goal))
    assert decision.action == "blocked"
    assert decision.rationale == f"holding {entity.entity_id} but no pending goal names it"


def test_the_id_keyed_path_does_not_move(monkeypatch, held_world):
    case, world, entity = held_world
    _DriftedProgress.rows = [_item(entity.entity_id, "tray_middle")]
    monkeypatch.setattr(RuntimeVerifier, "progress", _DriftedProgress)
    planner = RulePlanner(case.verify)
    goal = _goal_with(dict(entity.attributes), "tray_middle")

    decision = planner.decide(_context(case, world, goal))
    assert decision.action == "execute" and decision.execute.args["target_id"] == "tray_middle"


def test_the_plan_path_never_plans_a_step_naming_an_attribute(monkeypatch, held_world):
    case, world, entity = held_world
    _DriftedProgress.rows = [_item(_declared_key(entity), "tray_left")]
    monkeypatch.setattr(RuntimeVerifier, "progress", _DriftedProgress)
    planner = RulePlanner(case.verify)
    goal = _goal_with(dict(entity.attributes), "tray_left")

    steps = planner.plan(goal, world).steps
    assert steps == [], f"a pick/place step must name an entity, not {steps}"


def _declared_key(entity) -> str:
    """The literal-dict string the verifier writes into an unbound row's `entity_id`."""
    return str(dict(entity.attributes))