"""v0.7 contract tests: the v2 task table, and the two declaration forms it introduces.

Six properties, one per thing v0.7 P2 changed:

1. **c1's colour-only mention still says what v1's did** -- the utterance's bindings must be the
   same (object, region) pairs the hidden truth names, because P-A drops a *question*, never an
   *answer*;
2. **the other five cases are byte-identical between v1 and v2** -- D2'''' carried them over
   unchanged, and "unchanged" has to be checkable rather than asserted;
3. **v1 is still reproducible and still sealed** -- the same code path rebuilds v1's cases and
   they match the frozen file, so the v2 switch did not quietly rewrite history;
4. **the group form binds every member to one target**, refuses a count the scene cannot answer,
   and leaves a bare colour that matches two bodies an ambiguity (the refusal that found c6's
   collision in the first place);
5. **the v2 payload carries the two profiles** (P-C trigger premise, P-D demand) and the
   known-hard / unverified markers, because a bound that is not in the table is a bound nobody
   can re-derive;
6. **the live long-horizon table is v2 and the freeze is green on it**.

No test here spends a request or needs a camera.
"""
from __future__ import annotations

import json
import os

import pytest

from embodied_agent.core.interpreter import interpret
from embodied_agent.core.runtime import build_world_state
from agent_lab.evaluation.long_horizon_tasks import (
    LH_FROZEN_PATH, LH_V2_DECLARATIONS, LH_V2_KNOWN_HARD, LH_V2_UNCHANGED, build_long_horizon_set,
    check_lh_frozen, lh_manifest, v2_utterance)
from agent_lab.evaluation.run import build_scene, task_input
from agent_lab.evaluation.tasks import find_case

V1_PATH = os.path.join(os.path.dirname(LH_FROZEN_PATH), "frozen_long_horizon_v1.json")
C1 = "lh_c1_shared_pair_restore"
C3 = "lh_c3_capacity_and_shift"


def _case(case_id: str, version: str = "v2"):
    return next(c for c in build_long_horizon_set(version) if c.task_id == case_id)


def _bindings(case) -> list[tuple[str, str]]:
    """The (entity, target) pairs the utterance actually binds, through the real interpreter.

    A mention that carries attributes rather than an id is resolved here exactly the way the
    production code resolves it (`entity_id or bind_attributes`), because the **form** of the ref is
    allowed to change between v1 and v2 -- the colour-only mention binds `{"color": "purple"}`
    where the explicit one bound `{"color": "purple", "shape": "cylinder"}` -- while the body it
    points at is not allowed to.
    """
    from embodied_agent.core.verify import bind_attributes

    scene = build_scene(case)
    try:
        world = build_world_state(scene, 1, "obs_0001", case.verify)
        goal = interpret(task_input(case), world)
        resolved = []
        for assignment in goal.assignments:
            ref = assignment.entity
            entity_id = ref.entity_id or bind_attributes(dict(ref.attributes or {}), world)
            resolved.append((entity_id, assignment.target_id))
    finally:
        scene.close()
    return sorted(resolved)


def _truth(case) -> list[tuple[str, str]]:
    return sorted((a["entity_id"], a["target_id"])
                  for a in case.eval_spec.model_dump()["assignments"])


def test_c1_drops_the_shape_question_and_keeps_the_answer():
    v1, v2 = _case(C1, "v1"), _case(C1, "v2")
    assert v1.utterance != v2.utterance, "P-A must actually change c1's utterance"
    assert "紫色的圆柱" in v1.utterance and "紫色的圆柱" not in v2.utterance
    assert "紫色的物体" in v2.utterance
    # the same four (object, region) pairs, on both sides: the mention is narrower, the task is not
    assert _bindings(v2) == _bindings(v1) == _truth(v2), (_bindings(v2), _truth(v2))
    assert len(_truth(v2)) == 4, "c1 still asks for four bodies"


def test_the_five_carried_over_cases_are_byte_identical():
    v1 = {c.task_id: c.utterance for c in build_long_horizon_set("v1")}
    v2 = {c.task_id: c.utterance for c in build_long_horizon_set("v2")}
    changed = {k for k in v1 if v1[k] != v2[k]}
    assert changed == {C1}, f"only c1 may change; also changed: {sorted(changed)}"
    assert set(LH_V2_UNCHANGED) == set(v1) - {C1}
    for case_id in LH_V2_UNCHANGED:
        case = _case(case_id)
        assert case.events, f"{case_id} keeps its disturbance structure (principle 21(b))"


def test_v1_is_still_reproducible_and_still_sealed():
    with open(V1_PATH, encoding="utf-8") as f:
        sealed = json.load(f)
    recorded = sealed.pop("sha256")
    import hashlib
    assert hashlib.sha256(
        json.dumps(sealed, ensure_ascii=False, sort_keys=True, indent=1).encode("utf-8")
    ).hexdigest() == recorded, "the sealed v1 file must still hash to its own recorded value"
    frozen_cases = {c["task_id"]: c for c in sealed["cases"]}
    for case in build_long_horizon_set("v1"):
        assert case.utterance == frozen_cases[case.task_id]["utterance"]
        assert case.targets == frozen_cases[case.task_id]["targets"]


def test_the_group_form_binds_every_member_to_one_target():
    """Two yellows into one tray: two assignments, one target, and the goal is well-formed.

    Built against the real interpreter and a real scene, because the form's whole risk is that
    it quietly binds one member or drops one clause.
    """
    from embodied_agent.core.contracts import TaskInput as _TaskInput
    from embodied_agent.core.runtime import build_world_state as _build
    from agent_lab.evaluation.run import build_scene as _scene_of

    case = find_case(C3, ("long_horizon",))
    scene = _scene_of(case)
    try:
        world = _build(scene, 1, "obs_0001", case.verify)
    finally:
        scene.close()
    goal = interpret(_TaskInput(task_id="probe", utterance="把两个黄色物体放入中间托盘。"), world)
    assert not goal.ambiguous, goal.clarification_request
    yellows = sorted(a.entity.entity_id for a in goal.assignments)
    assert len(yellows) == 2 and all(y.startswith("obj_yellow") for y in yellows), yellows
    assert {a.target_id for a in goal.assignments} == {"tray_middle"}


def test_a_count_the_scene_cannot_answer_asks_rather_than_guesses():
    from embodied_agent.core.contracts import TaskInput as _TaskInput
    from embodied_agent.core.runtime import build_world_state as _build
    from agent_lab.evaluation.run import build_scene as _scene_of

    case = find_case(C3, ("long_horizon",))
    scene = _scene_of(case)
    try:
        world = _build(scene, 1, "obs_0001", case.verify)
    finally:
        scene.close()
    # c3 shows exactly two yellows, so "three" is a declaration the scene cannot answer
    goal = interpret(_TaskInput(task_id="probe", utterance="把三个黄色物体放入中间托盘。"), world)
    assert goal.ambiguous and "2" in (goal.clarification_request or "")
    # and a bare colour that matches two bodies is still a refusal -- that refusal is what found
    # c6's collision, and widening the bare form would take it away
    bare = interpret(_TaskInput(task_id="probe", utterance="把黄色物体放入中间托盘。"), world)
    assert bare.ambiguous and "matches 2 entities" in (bare.clarification_request or "")


def test_a_group_whose_members_disagree_on_the_target_is_refused_at_build_time():
    """The group mention says "all of these go here"; if they do not, rendering it would
    rewrite the hidden truth. The refusal is a `ValueError`, not a silently wrong utterance."""
    case = find_case(C3, ("long_horizon",))
    objs = [o for o in case.objects if o["entity_id"] in case.targets]
    assignment = {a["entity_id"]: a["target_id"]
                  for a in case.eval_spec.model_dump()["assignments"]}
    assert assignment["obj_yellow_1"] != assignment["obj_yellow_6"], \
        "this test only means anything while the two yellows really do go to different trays"
    with pytest.raises(ValueError, match="group declaration"):
        v2_utterance(objs, assignment, {"groups": [
            {"members": ["obj_yellow_1", "obj_yellow_6"]}]})


def test_the_v2_payload_carries_the_two_profiles_and_the_markers():
    payload = lh_manifest()
    assert payload["table_version"] == "v2"
    assert payload["sealed_v1_sha256"], "v2 must name the sealed table it replaces"
    profiles = payload["profiles"]
    assert profiles.get("cases"), "P-C/P-D profiles must be in the table, not in a report"
    for case_id, reading in profiles["cases"].items():
        assert "trigger_premise" in reading and "demand" in reading, case_id
        assert reading["trigger_premise"]["has_denominator_at_t0"] in (True, False)
    assert set(LH_V2_KNOWN_HARD) >= {C3, "lh_c6_two_disruptions"}
    assert "#25" in LH_V2_KNOWN_HARD[C3] and "#24" in LH_V2_KNOWN_HARD["lh_c6_two_disruptions"]
    assert LH_V2_DECLARATIONS[C1]["re_adjudicated"] is True
    assert all(LH_V2_DECLARATIONS[c]["re_adjudicated"] is False for c in LH_V2_UNCHANGED)


def test_the_live_table_is_v2_and_the_freeze_is_green():
    assert LH_FROZEN_PATH.endswith("frozen_long_horizon_v2.json"), LH_FROZEN_PATH
    ok, message = check_lh_frozen()
    assert ok, message
    live = lh_manifest()
    assert _case(C1).utterance == live["cases"][0]["utterance"]