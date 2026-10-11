"""v0.6 H2 contract test: the dependency graph is derived, never authored by the first snapshot.

v0.5's A2 left H2 as a reading -- "the model writes edges only in a replan; 187 initial views,
zero counterexamples" -- and SPEC §5 asks for it to become a permanent contract. Writing it
down forced the question the reading had been hiding, and the answer is sharper than the
reading was:

**the edges are not the model's.** `planning/subgoals.py` derives them. `derive()` asks the
*placement instrument* how many slots a region really has (`_capacity_dependencies`) and asks
whether one body is sitting where another needs to go (the displacement rule, whose note is the
deterministic sentence `"{blocker} was displaced out of {region} to let {other} in and must be
restored before the task ends"` -- the exact string in all three archived edges). The model's
own plan payload produces *steps*, never the work graph.

So H2 is not "the model chose not to write edges at t0"; it is **"at t0 there is nothing to
derive one from"**: no body has been displaced yet, and the frozen long-horizon trays hold far
more clear slots than they owe objects (6-47 per victim at this object scale, per the
deriver's own note). Two halves are asserted here, and the second is the one that keeps the
first from being vacuous:

1. over **every frozen long-horizon case**, the initial derivation authors **no** dependency
   edge -- the corpus reading, reproduced from the task list rather than from the archives;
2. the rule that would author one is **live**: with a placement instrument that reports zero
   feasible slots, `derive()` authors `resource` edges on the same snapshot.

Together they say what the archive shows and why: an initial view has no edges because the
world at t0 cannot produce one, not because anything suppressed it.

No request is spent; the cases are built from the frozen task list and the physics scene the
runner itself builds.
"""
from __future__ import annotations

import pytest

from embodied_agent.core.interpreter import interpret
from embodied_agent.core.placement_planner import PlacementPlanner
from embodied_agent.core.verify import build_world_state
from embodied_agent.evaluation.run import build_scene, task_input
from embodied_agent.evaluation.tasks import build_set
from embodied_agent.planning.subgoals import derive

LONG_HORIZON = "long_horizon"


def _initial_state(task_id: str):
    """Exactly what a plan's first view is derived from: the t0 snapshot of the frozen case."""
    case = next(c for c in build_set(LONG_HORIZON) if c.task_id == task_id)
    scene = build_scene(case)
    try:
        world = build_world_state(scene, 1, "obs_0001", case.verify)
        goal = interpret(task_input(case), world)
        return goal, world, case
    finally:
        scene.close()


def test_no_frozen_long_horizon_case_derives_an_edge_at_t0():
    """Acceptance 1: the H2 criterion, re-derived from the task list rather than read off the
    archives -- so a new case added to the frozen table is judged the moment it is added."""
    offenders = {}
    for case in build_set(LONG_HORIZON):
        goal, world, _case = _initial_state(case.task_id)
        derivation = derive(goal, world, task_input(case))
        if derivation.dependencies:
            offenders[case.task_id] = [d.model_dump(mode="json")
                                       for d in derivation.dependencies]
    assert offenders == {}, f"an initial view derived an edge: {sorted(offenders)}"


@pytest.mark.parametrize("case_id", ["lh_c2_displaced_completion", "lh_c3_capacity_and_shift"])
def test_the_rule_is_live_on_the_same_world_where_it_found_none(case_id):
    """Acceptance 2: the first test is only worth anything if the derivation *can* author an
    edge on the very kind of world where it found none.

    The displacement rule needs two things the t0 table cannot have: a region **two** of the
    goal's own assignments name, with one of its bodies already **sitting inside** it
    (`occupants(world, region)`), and no feasible slot left for the other. So this takes the
    case's own goal, picks its first tray that two assignments name, seats one of those bodies
    in it, and stages a refusal for the other -- refusing exactly one (object, region) pair and
    measuring the real geometry for the temporary move that makes the recovery obligation
    answerable. (The branch that fires when *no* region can receive the blocker deliberately
    records an unanswerable obligation instead of an edge; that is a different claim and is not
    what this test is about.)
    """
    from embodied_agent.core.verify import RuntimeVerifier

    goal, world, case = _initial_state(case_id)
    owed = {}
    for item in RuntimeVerifier(world).progress(goal):
        if item.entity_id:
            owed.setdefault(item.target_id, []).append(item.entity_id)
    contested = next((t for t, eids in sorted(owed.items()) if len(eids) >= 2), None)
    assert contested, f"{case_id} has no tray two assignments name; pick another case"
    blocker, blocked = owed[contested][0], owed[contested][1]

    scene = build_scene(case)
    try:
        planner = PlacementPlanner(scene, config=case.verify)
        sitting = _seat_in(world, case, blocker, contested)
        staged = _TrayFullFor(planner, blocked, contested, "staged: the region is occupied")
        fired = derive(goal, sitting, task_input(case), planner=staged)
        assert fired.dependencies, \
            "the displacement rule stopped firing; H2 would be vacuous"
        # Which of the two rules fires is a property of the case (c2 stages the displacement
        # shape, c3 also contests tray_left outright and the capacity rule answers first);
        # what the contract claims is that *some* rule can turn this world into a graph that is
        # not a flat assignment list, and that the edge says which region is the constraint.
        assert {d.kind.value for d in fired.dependencies} <= {"recovery", "resource", "state"}
        assert any((d.note or "") and contested in d.note for d in fired.dependencies), \
            [d.note for d in fired.dependencies]
    finally:
        scene.close()


class _TrayFullFor:
    """A placement instrument that refuses exactly one (object, region) pair.

    The real registry is used for everything else, so the derivation still measures real
    geometry for the temporary move that makes the recovery obligation answerable -- the
    branch that fires when no other region can receive the blocker deliberately records an
    unanswerable obligation instead of inventing an edge, and a stand-in that refused
    everything would test that branch rather than this one.
    """

    def __init__(self, inner, entity_id: str, target_id: str, reason: str):
        self.inner = inner
        self.entity_id = entity_id
        self.target_id = target_id
        self.reason = reason

    def generate(self, target_id, entity_id, world, limit=8):
        cands = self.inner.generate(target_id, entity_id, world, limit=limit)
        if entity_id == self.entity_id and target_id == self.target_id:
            return cands
        return cands

    def recheck(self, cand, world, hold_entity=True):
        check = self.inner.recheck(cand, world, hold_entity=hold_entity)
        if cand.entity_id == self.entity_id and cand.target_id == self.target_id:
            from embodied_agent.core.placement_planner import CandidateCheck

            return CandidateCheck(check.candidate, [self.reason])
        return check


def _seat_in(world, case, entity_id: str, target_id: str):
    """The t0 snapshot with one body set down in the region its own goal names.

    Written as a copy, never as a simulator step: the point is what the *deriver* sees, and a
    physics run would bring its own trajectory along with it.
    """
    from embodied_agent.core.contracts import EntityState, SupportEvidence, Vec3

    region = next(t for t in world.targets if t.target_id == target_id)
    cx, cy = region.center.x, region.center.y
    entities = []
    for e in world.entities:
        if e.entity_id != entity_id:
            entities.append(e)
            continue
        entities.append(e.model_copy(update={
            "pose": e.pose.model_copy(update={"position": Vec3(x=cx, y=cy, z=region.floor_top_z)})
            if e.pose else None,
            "supported_by": target_id,
            "support": SupportEvidence(surface=target_id, z_m=region.floor_top_z,
                                       confidence=1.0, method="test:seated"),
        }))
    return world.model_copy(update={"entities": entities})