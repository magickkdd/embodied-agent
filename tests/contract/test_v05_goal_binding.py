"""v0.5 P3 contract tests: one binding question, one binding rule (D3'', option B1).

What A1 measured (v0.5 phase log, "P2 A1 读数"): the bottleneck ring in all eight dead E2'
episodes is **b, grounding/binding** — 8/8, with ring a (whole-episode detection) and ring d
(prompt/parse, 92/92 clean requests) at zero. The mechanism is visible in the records: the
VLM saw the c3 yellow cube in **7 of 7 rounds** and called it a `cuboid` every time, so the
one assignment that names it (`{color: yellow, shape: cube}`) never resolved, the object left
the world the loop could act on, and the episode died with the other five items fine.

The defect behind that is not the reader's. It is that the same question -- "which declared
body does this assignment name?" -- is answered by **two different rules**:

* the grounding bridge (`GroundingMap._lookup`) says, in as many words, that *a unique colour
  wins whatever the shape says -- a misread shape must not override the bridge*;
* the goal-side resolver (`RuntimeVerifier.bind` -> `bind_attributes`) requires every declared
  attribute to equal the **frame's measured** attribute and exactly one entity to match, so a
  misread shape there silently withdraws the body.

These tests pin the fix that follows from the attribution -- the goal side asks the bridge,
and the bridge's answer still has to be visible in the current snapshot -- and, just as
importantly, pin what it must **not** do:

* it must not resurrect a body the frame cannot currently see (that is ring a, not ring b,
  and SPEC v0.5 §4.16 puts a second ring out of authorisation);
* it must not weaken the composite key for a colour the declaration declares twice;
* the privileged channel, which has no bridge and whose behaviour is the 4/4 control, must
  read exactly as it did.

No test here spends a request; the worlds are hand-built from `EntityState` records the way
`test_v04_grounding_keys.py` builds them.
"""
from __future__ import annotations

from embodied_agent.core.contracts import EntityRef, EntityState, GoalAssignment, GoalSpec, WorldState
from embodied_agent.core.planner import RulePlanner
from embodied_agent.core.verify import RuntimeVerifier
from embodied_agent.perception.grounding import GROUNDING, UNGROUNDED, GroundingMap, ground_state

#: `lh_c1`'s declaration: four bodies, four colours, so every colour is unique and the
#: composite key is never consulted (v0.4 R3 rule 1).
C1_OBJECTS = [
    {"entity_id": "obj_green_1", "attributes": {"color": "green"}, "shape": "cube"},
    {"entity_id": "obj_blue_2", "attributes": {"color": "blue"}, "shape": "cuboid"},
    {"entity_id": "obj_yellow_3", "attributes": {"color": "yellow"}, "shape": "cube"},
    {"entity_id": "obj_purple_4", "attributes": {"color": "purple"}, "shape": "cylinder"},
]

#: `lh_c3`'s declaration: two yellow bodies, a cube and a cuboid, which is what needs the
#: (colour, shape) key at all.
C3_OBJECTS = [
    {"entity_id": "obj_yellow_1", "attributes": {"color": "yellow"}, "shape": "cube"},
    {"entity_id": "obj_purple_2", "attributes": {"color": "purple"}, "shape": "cube"},
    {"entity_id": "obj_red_3", "attributes": {"color": "red"}, "shape": "cuboid"},
    {"entity_id": "obj_green_4", "attributes": {"color": "green"}, "shape": "cylinder"},
    {"entity_id": "obj_blue_5", "attributes": {"color": "blue"}, "shape": "cube"},
    {"entity_id": "obj_yellow_6", "attributes": {"color": "yellow"}, "shape": "cuboid"},
]


def _entity(entity_id: str, color: str, shape: str) -> EntityState:
    return EntityState(entity_id=entity_id, attributes={"color": color, "shape": shape})


def _world(*entities: EntityState) -> WorldState:
    return WorldState(state_version=7, sim_time=1.0, wall_time=1.0, entities=list(entities),
                      targets=[])


def _goal(attrs: dict[str, str], target_id: str = "tray_right") -> GoalSpec:
    return GoalSpec(assignments=[GoalAssignment(entity=EntityRef(attributes=attrs),
                                                 target_id=target_id)])


PURPLE_BY_ATTRIBUTES = {"color": "purple", "shape": "cylinder"}   # what c1's task declares
YELLOW_CUBE_BY_ATTRIBUTES = {"color": "yellow", "shape": "cube"}  # what c3's task declares


# ---------------------------------------------------------------- the fix ----

def test_a_misread_shape_does_not_withdraw_a_uniquely_coloured_body():
    """The E2' death, reduced to one call: the frame grounded the purple body (so the world
    carries the declared id) but measured it as a `cuboid`. Before the fix the assignment's
    `{purple, cylinder}` matched nothing and the body left the loop's world; now the bridge
    answers, because a colour the declaration gives once needs no second key."""
    gmap = GroundingMap.from_objects(C1_OBJECTS)
    world = _world(_entity("obj_green_1", "green", "cube"),
                   _entity("obj_purple_4", "purple", "cuboid"))     # the misread shape
    verifier = RuntimeVerifier(world, gmap=gmap)

    assert verifier.bind(_goal(PURPLE_BY_ATTRIBUTES).assignments[0]) == "obj_purple_4"
    (item,) = verifier.progress(_goal(PURPLE_BY_ATTRIBUTES))
    assert "entity_binding" not in (item.unmeasured or [])
    assert item.entity_id == "obj_purple_4"


def test_the_bound_body_is_offered_to_the_decider_as_work():
    """Binding is not a report: an assignment that resolves is `pending`, and the rule
    planner picks it. This is the step whose absence made c3's episodes end in `blocked`
    with three objects nobody could act on."""
    gmap = GroundingMap.from_objects(C1_OBJECTS)
    world = _world(_entity("obj_purple_4", "purple", "cuboid"))
    planner = RulePlanner(gmap=gmap)

    assert planner.pending_assignments(_goal(PURPLE_BY_ATTRIBUTES),
                                       world) == [("obj_purple_4", "tray_right")]


def test_c3s_yellow_cube_binds_when_the_two_yellows_were_told_apart():
    """The other half of the E2' evidence, and the case the composite key exists for: when
    the frame did distinguish c3's two yellow bodies, the cube resolves through the same
    bridge rule as any other body."""
    gmap = GroundingMap.from_objects(C3_OBJECTS)
    world = _world(_entity("obj_yellow_1", "yellow", "cube"),
                   _entity("obj_yellow_6", "yellow", "cuboid"))
    verifier = RuntimeVerifier(world, gmap=gmap)

    assert verifier.bind(_goal(YELLOW_CUBE_BY_ATTRIBUTES, "tray_middle")
                         .assignments[0]) == "obj_yellow_1"


# ----------------------------------------------------- what it must not do ----

def test_an_ambiguous_colour_is_not_split_by_the_shape_the_frame_got_wrong():
    """The refusal narrows, it does not disappear (v0.4 R3 rule 3), and this is E2''s c3
    situation exactly: the frame saw both yellow bodies and called them **both** cuboid, so
    the declared `{yellow, cube}` matches nothing the bridge can name and nothing the
    attribute match can single out. The assignment stays unbound and says so."""
    gmap = GroundingMap.from_objects(C3_OBJECTS)
    world = _world(_entity("seen:yellow", "yellow", "cuboid"),
                   _entity("seen:yellow_2", "yellow", "cuboid"))
    verifier = RuntimeVerifier(world, gmap=gmap)

    assert verifier.bind(_goal(YELLOW_CUBE_BY_ATTRIBUTES, "tray_middle").assignments[0]) is None
    (item,) = verifier.progress(_goal(YELLOW_CUBE_BY_ATTRIBUTES, "tray_middle"))
    assert "entity_binding" in (item.unmeasured or []), "an unbindable assignment says so"
    assert RulePlanner(gmap=gmap).pending_assignments(
        _goal(YELLOW_CUBE_BY_ATTRIBUTES, "tray_middle"), world) == []


def test_an_ungrounded_frame_name_is_not_promoted_by_the_bridge():
    """A body the bridge refused to name keeps its frame name and its ungrounded mark; the
    goal-side fix reads the bridge's answer, it does not re-run grounding behind its back.
    The refusal is the ordinary one: c3's yellow is ambiguous, and a frame that measured no
    usable shape has nothing to split it with."""
    gmap = GroundingMap.from_objects(C3_OBJECTS)
    world = ground_state(_world(_entity("seen:yellow", "yellow", "unknown")), gmap)
    (yellow,) = world.entities
    assert yellow.entity_id == "seen:yellow"
    assert yellow.attributes[GROUNDING] == UNGROUNDED

    bound = RuntimeVerifier(world, gmap=gmap).bind(
        _goal(YELLOW_CUBE_BY_ATTRIBUTES, "tray_middle").assignments[0])
    assert bound != "obj_yellow_1", "the fix does not name a body the frame did not ground"


def test_a_body_the_frame_cannot_see_is_not_resurrected_by_the_declaration():
    """Ring a stays ring a. The declaration knows that `obj_purple_4` exists; a frame that
    did not detect it this round must not put it back, or the fix would be quietly fixing
    the detection ring too -- which SPEC v0.5 §4.16 puts out of authorisation."""
    gmap = GroundingMap.from_objects(C1_OBJECTS)
    world = _world(_entity("obj_green_1", "green", "cube"))    # purple not detected
    verifier = RuntimeVerifier(world, gmap=gmap)

    assert verifier.bind(_goal(PURPLE_BY_ATTRIBUTES).assignments[0]) is None
    assert RulePlanner().pending_assignments(_goal(PURPLE_BY_ATTRIBUTES), world) == []


def test_the_privileged_channel_reads_exactly_as_it_did():
    """No bridge, no new rule. On a channel that reports the declared attributes there is
    nothing to repair, and the control that makes every camera reading interpretable (4/4 in
    E2') must not move by a single binding."""
    world = _world(_entity("obj_purple_4", "purple", "cylinder"))
    verifier = RuntimeVerifier(world)                          # no gmap: the v0.4 channel
    assert verifier.bind(_goal(PURPLE_BY_ATTRIBUTES).assignments[0]) == "obj_purple_4"

    misread = _world(_entity("obj_purple_4", "purple", "cuboid"))
    assert RuntimeVerifier(misread).bind(_goal(PURPLE_BY_ATTRIBUTES).assignments[0]) is None, \
        "without a bridge the old rule stands, exactly as it did before v0.5"


def test_the_bridge_itself_is_untouched():
    """D3'' authorised the goal-side call, not a change to the map: a colour-unique map must
    still hash as it did in v0.4, or every batch identity that quotes `map_sha256` would
    move for a reason nobody asked for."""
    gmap = GroundingMap.from_objects(C1_OBJECTS)
    assert gmap.bind("purple", "cylinder") == "obj_purple_4"
    assert gmap.bind("purple", "cuboid") == "obj_purple_4", "rule 1: shape never overrides"
    assert gmap.key_of() == {"obj_green_1": "colour", "obj_blue_2": "colour",
                             "obj_yellow_3": "colour", "obj_purple_4": "colour"}
    assert GroundingMap.from_objects(C3_OBJECTS).key_of() == {
        "obj_yellow_1": "colour_shape", "obj_yellow_6": "colour_shape",
        "obj_purple_2": "colour", "obj_red_3": "colour", "obj_green_4": "colour",
        "obj_blue_5": "colour"}