"""One-shot plan baseline and state-aware plan validation (SPEC 5.3, 8, 11.2).

`RulePlanner` is the Mode A control condition: it reads the goals and the state
once, emits a full plan, and does not revise it. It is *not* a general Chinese
NL parser and it is not smarter than the model on purpose.

`PlanValidator` checks a plan against the **latest** snapshot rather than the
version the plan was generated from, so advancing state versions alone never
invalidate an action that is still legal (SPEC 6.1). It uses no scoring truth.
"""
from __future__ import annotations

import ast

from .contracts import (
    Decision,
    DecisionContext,
    DecisionExecute,
    GoalSpec,
    Plan,
    PlanStep,
    PredicateVerdict,
    VerifyConfig,
    WorldState,
)
from .verify import RuntimeVerifier

REQUIRED_ARGS = {
    "pick": {"object_id"},
    "place": {"object_id", "target_id"},
    "observe": set(),
    "safe_retreat": set(),
}
OPTIONAL_ARGS = {
    "pick": {"grasp_candidate_index"},
    "place": {"candidate_id"},
    "observe": {"view"},
    "safe_retreat": set(),
}


class PlanValidator:
    """Schema, reference and symbolic-precondition checks against one snapshot.

    Two defects fixed here (SPEC 2.1, 8): targets are read from the world
    instead of a hard-coded whitelist, and the hold state is tracked through the
    plan instead of assuming the gripper starts empty — a plan that begins with
    `place` is legal when the object is already held."""

    def __init__(self, world: WorldState, config: VerifyConfig | None = None):
        self.world = world
        self.config = config or VerifyConfig()

    def validate(self, plan: Plan) -> tuple[bool, list[str]]:
        errs = list(plan.validate_schema())
        if plan.schema_version != self.world.schema_version:
            errs.append(f"unsupported schema_version {plan.schema_version}")
        if not plan.steps:
            errs.append("empty plan (a legal no-op must be represented explicitly)")

        known_entities = {e.entity_id for e in self.world.entities}
        known_targets = {t.target_id for t in self.world.targets}
        held = self.world.held_object
        unknown_hold = held == "unknown"

        for s in plan.steps:
            if s.skill not in REQUIRED_ARGS:
                errs.append(f"step {s.id}: unknown skill {s.skill}")
                continue
            for a in REQUIRED_ARGS[s.skill] - set(s.args):
                errs.append(f"step {s.id}: missing required argument {a} for {s.skill}")
            for a in set(s.args) - REQUIRED_ARGS[s.skill] - OPTIONAL_ARGS[s.skill]:
                errs.append(f"step {s.id}: unexpected argument {a} for {s.skill}")
            if s.skill == "pick" and s.args.get("object_id") not in known_entities:
                errs.append(f"step {s.id}: object {s.args.get('object_id')} is not in "
                            f"observation {self.world.observation_ref}")
            if s.skill == "place":
                if s.args.get("object_id") not in known_entities:
                    errs.append(f"step {s.id}: object {s.args.get('object_id')} is not in "
                                f"observation {self.world.observation_ref}")
                if s.args.get("target_id") not in known_targets:
                    errs.append(f"step {s.id}: target {s.args.get('target_id')} is not in "
                                f"observation {self.world.observation_ref}")

            # symbolic hold tracking against the snapshot's initial hold state
            if s.skill == "pick":
                oid = s.args.get("object_id")
                if unknown_hold:
                    errs.append(f"step {s.id}: pick while the hold state is unknown")
                elif held is not None and held != oid:
                    errs.append(f"step {s.id}: cannot pick {oid}, gripper holds {held}")
                else:
                    held = oid
            elif s.skill == "place":
                oid = s.args.get("object_id")
                if unknown_hold:
                    errs.append(f"step {s.id}: place while the hold state is unknown")
                elif held != oid:
                    errs.append(f"step {s.id}: place {oid} before it is held "
                                f"(gripper holds {held!r})")
                else:
                    held = None
        return len(errs) == 0, errs


def _declared_attributes(entity_id: str) -> dict | None:
    """The attribute pair an *unbound* progress row carries, or `None` if it names an entity.

    A row whose binding could not be measured writes the declaration's own attributes into its
    `entity_id` as a literal dict string (`"{'shape': 'cube', 'color': 'green'}"`) -- that is what
    the five archived held-orphan episodes show, and what `entity_binding` in a row's unmeasured
    list means. Reading those attributes back is how an unbound obligation can still be matched
    against the object in the hand.

    Parsing a string is a compromise, and it is made here rather than by adding a field to the
    progress record: the record classes are inside the frozen schema
    (`core/v02.schema_fingerprint()` must stay item-by-item equal), while this module is not.
    A row that does not parse as a dict is simply an id, which is the overwhelmingly common case.
    """
    text = str(entity_id or "").strip()
    if not text.startswith("{"):
        return None
    try:
        parsed = ast.literal_eval(text)
    except (ValueError, SyntaxError):
        return None
    return parsed if isinstance(parsed, dict) and parsed else None


class RulePlanner:
    """Generates one pick/place sequence per unsatisfied assignment.

    Progress is recomputed from the *current* snapshot every time `plan` is
    called, with the same verifier the runtime uses — there is no permanent
    "already placed" flag (SPEC 5.1)."""

    def __init__(self, config: VerifyConfig | None = None, *, gmap=None):
        self.config = config or VerifyConfig()
        #: the grounding bridge of the channel this planner reads (v0.5 P3, D3''). It is
        #: here for the same reason it is on the verifier: an assignment is resolved by the
        #: declaration's own rule, and a planner that resolved it by another would offer the
        #: decider a different set of pending goals than the context it was handed reports.
        self.gmap = gmap

    def pending_assignments(self, goal: GoalSpec, world: WorldState, *,
                            include_unbound: bool = False) -> list[tuple[str, str]]:
        """The assignments this snapshot has not measured satisfied, as `(entity, region)` pairs.

        `include_unbound` is v0.8 D2''''': an assignment whose *binding* could not be measured is
        still an obligation, and dropping it turned a binding drift into a dead end -- the five
        archived held-orphan episodes ended as `blocked` because the held object's row had fallen
        back to its declared attributes and `world.has_entity("<attribute dict>")` is false, so
        the row left this list and the held check had nothing to match.

        The default stays `False` for the **plan** path: a `PlanStep` names an entity, so an
        attribute-keyed row must not become a `pick(object_id="{...}")` step. Only the decision
        seam opts in, which is where the dead end lived.
        """
        v = RuntimeVerifier(world, self.config, gmap=self.gmap)
        pending = []
        for item in v.progress(goal):
            # `unknown` is pending as well: unmeasurable is not satisfied
            if item.value == PredicateVerdict.true:
                continue
            if world.has_entity(item.entity_id):
                pending.append((item.entity_id, item.target_id))
                continue
            if include_unbound and _declared_attributes(item.entity_id):
                pending.append((item.entity_id, item.target_id))
        return pending

    def _target_for_held(self, held: str, goal: GoalSpec, world: WorldState) -> str | None:
        """Which region a pending goal names for the object in the hand.

        Ids first, then attributes. The attribute fallback is the same declaration semantics the
        reader and the verifier use (a row declares `{'color': 'green', 'shape': 'cube'}` and the
        held body carries those attributes), so a drift in the *binding* cannot hide an
        obligation that is plainly still pending -- which is exactly the shape v0.8 RQ21 measured
        in five episodes.
        """
        pending = self.pending_assignments(goal, world, include_unbound=True)
        target = next((t for e, t in pending if e == held), None)
        if target is not None:
            return target
        entity = next((e for e in world.entities if e.entity_id == held), None)
        if entity is None:
            return None
        for row_entity, row_target in pending:
            declared = _declared_attributes(row_entity)
            if declared and all(entity.attributes.get(k) == v for k, v in declared.items()):
                return row_target
        return None

    def plan(self, goal: GoalSpec, world: WorldState, plan_id: str | None = None) -> Plan:
        """Steps name the target region, not a slot.

        A one-shot plan cannot know which slot will be free when the gripper
        arrives, and freezing a t0 slot would punish the baseline for the state
        its own plan had to anticipate (SPEC 5.5). Both modes therefore share the
        documented fallback resolution rule, and its use is recorded per step.
        """
        pending = self.pending_assignments(goal, world)
        steps: list[PlanStep] = []
        for i, (eid, tid) in enumerate(pending):
            steps.append(PlanStep(id=f"s{2 * i}", skill="pick", args={"object_id": eid}))
            steps.append(PlanStep(id=f"s{2 * i + 1}", skill="place",
                                  args={"object_id": eid, "target_id": tid}))
        return Plan(
            plan_id=plan_id or f"p_rule_{len(pending)}",
            based_on_state_version=world.state_version,
            goal_ref=goal.goal_id,
            steps=steps,
        )

    def decide(self, ctx: DecisionContext, prefer: str | None = None) -> Decision:
        """One action for one context: the deterministic offline control policy.

        This is the single implementation of the rule policy — the offline mode B
        source and the offline fixture planner both reach the decision through it,
        so "the rule baseline" cannot mean two slightly different things in two
        files. It reads only the context: pending goals and the measured hold
        state decide, never a plan of its own.
        """
        pending = self.pending_assignments(ctx.goal, ctx.world)
        if prefer:
            pending.sort(key=lambda t: (t[0] != prefer, t[0]))
        held = ctx.world.held_object
        if isinstance(held, str) and held and held != "unknown":
            # v0.8 D2''''': ids first, then the declared attributes of an unbound row -- five
            # archived episodes ended as `blocked` because the held object's row had drifted to
            # its attributes and nothing matched it by id.
            target = self._target_for_held(held, ctx.goal, ctx.world)
            if target is None:
                return _control(ctx, "blocked", f"holding {held} but no pending goal names it")
            return _execute(ctx, "place", {"object_id": held, "target_id": target},
                            f"place {held} into {target}")
        if not pending:
            return _control(ctx, "finish", "every assignment measured satisfied")
        eid, _tid = pending[0]
        return _execute(ctx, "pick", {"object_id": eid}, f"pick {eid}")


def _execute(ctx: DecisionContext, skill: str, args: dict, why: str) -> Decision:
    return Decision(context_id=ctx.context_id, based_on_state_version=ctx.state_version,
                    goal_ref=ctx.goal.goal_id, action="execute",
                    execute=DecisionExecute(skill=skill, args=args),
                    rationale=why, evidence_refs=[ctx.observation_ref])


def _control(ctx: DecisionContext, action: str, why: str) -> Decision:
    return Decision(context_id=ctx.context_id, based_on_state_version=ctx.state_version,
                    goal_ref=ctx.goal.goal_id, action=action, rationale=why,
                    evidence_refs=[ctx.observation_ref],
                    missing_information=why if action == "clarify" else None)


class OneShotPlanSource:
    """Mode A decision source: emit the pre-computed steps, fixed repeat rule,
    no revision (SPEC 11.2).

    The only reaction it is allowed is the frozen one: when a step that really
    executed fails, and the action was not rejected on preconditions, submit the
    identical skill / object / candidate at most `per_action_extra_repeats` more
    times, then stop trying. It never adds an action, never reorders, never
    chooses a different target, and at the end of the plan it asks for `finish`
    so the agent-side goals are checked under the same protocol as Mode B.
    """

    provider = "one_shot_plan"
    # a class attribute, not an instance one: a subclass that reports the real
    # provider's cumulative counter overrides it with a property
    http_requests = 0

    def __init__(self, plan: Plan, per_action_extra_repeats: int = 2):
        self.plan = plan
        self.per_action_extra_repeats = per_action_extra_repeats
        self._index = 0
        self._repeats = 0
        self._pending_step: PlanStep | None = None

    def decide(self, ctx: DecisionContext) -> Decision:
        if self._pending_step is not None:
            self._settle_pending(ctx.last_feedback)
        if self._pending_step is None:
            self._pending_step = self._pop_step()
        step = self._pending_step
        if step is None:
            return self._finish(ctx, "one-shot plan exhausted")
        self._pending_step = step
        candidate_id = step.args.get("candidate_id")
        args = {k: v for k, v in step.args.items() if k != "candidate_id"}
        return Decision(
            context_id=ctx.context_id, based_on_state_version=ctx.state_version,
            goal_ref=self.plan.goal_ref, action="execute",
            execute=DecisionExecute(skill=step.skill, args=args, candidate_id=candidate_id),
            rationale=f"one-shot step {step.id}, planned at state v"
                      f"{self.plan.based_on_state_version}, repeat {self._repeats}",
            evidence_refs=[ctx.observation_ref],
        )

    def _settle_pending(self, fb) -> None:
        if fb is None or fb.status in ("model_error",):
            return                      # nothing was executed; the step stays pending
        if fb.status == "completed" or fb.status == "rejected":
            # rejected = a guard the baseline is not allowed to argue with
            self._pending_step, self._repeats = None, 0
            return
        if fb.status in ("failed", "timeout", "uncertain"):
            if self._repeats >= self.per_action_extra_repeats:
                self._pending_step, self._repeats = None, 0
            else:
                self._repeats += 1      # the one permitted reaction: identical repeat

    def _finish(self, ctx: DecisionContext, why: str) -> Decision:
        return Decision(context_id=ctx.context_id, based_on_state_version=ctx.state_version,
                        goal_ref=self.plan.goal_ref, action="finish", rationale=why,
                        evidence_refs=[ctx.observation_ref])

    def _pop_step(self) -> PlanStep | None:
        if self._index >= len(self.plan.steps):
            return None
        step = self.plan.steps[self._index]
        self._index += 1
        self._repeats = 0
        return step
