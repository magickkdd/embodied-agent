"""v0.5 R1 contract tests: a blocked episode carries its reason on the summary face.

The finding (v0.4 report §8 residual 21, observed in E2'): the `blocked` branch of
`core/runtime.py` closed the episode with `_finalize(..., TerminalStatus.failed, None,
"blocked by model", mode)`. `failure_type=None` by design — a model that gives up is not
one of the frozen `FailureCode` values, and v0.5 SPEC §2.2 keeps the enum closed — but
`termination_reason` is never written on that path either, so the *result object* and the
episodes.csv/episode_summary row read "failed, for no stated reason" while the reason sits
one layer down in the event stream. E2' has four such rows (c3, stub and vlm, two repeats
each); residual 18's in-episode cousin, one level further in.

What R1 does, and what these tests pin:

1. a blocked episode's `termination_reason` is non-empty and equals the reason the event
   stream recorded — one account, two faces, not two accounts;
2. `failure_type` stays `None`: the fix is not "add a failure code", which would put an
   enum value into event and result payloads and read as a re-freeze (SPEC §2.2);
3. the other terminal paths do not move — `clarify` still carries `AMBIGUOUS_TASK` plus
   the missing information, a success carries neither, and v0.4 R1's ledger-coverage
   contract (`tests/contract/test_v04_infra_ledger.py`) is untouched by this file;
4. a blocked decision that states no reason still ends with *some* reason, because
   "non-empty" is the property the summaries are read for; the fallback names the model's
   silence rather than inventing one.

Test 1 is the red one: on the pre-R1 code it reads `None`. No test here spends a request;
the blocked decision is injected at the source seam, which is what `tests/conftest.py`'s
`run_case` is for.
"""
from __future__ import annotations

from embodied_agent.core.contracts import Decision
from embodied_agent.core.runtime import BLOCKED_FALLBACK_REASON as FALLBACK_REASON


class BlockedSource:
    """A decision source that gives up, the way `RulePlanner.decide` does when it is
    holding something no pending goal names — and the way a model can. Only the
    decision source is substituted; everything else is the production loop."""

    provider = "blocked_fixture"
    prompt_tokens = 0
    completion_tokens = 0

    def __init__(self, rationale: str):
        self.rationale = rationale
        self.calls = 0
        self.http_requests = 0

    def decide(self, ctx):
        self.calls += 1
        return Decision(context_id=ctx.context_id, based_on_state_version=ctx.state_version,
                        goal_ref=ctx.goal.goal_id, action="blocked",
                        rationale=self.rationale, evidence_refs=[ctx.observation_ref])


def test_a_blocked_episode_states_why_on_the_result_object(run_case):
    """Acceptance 1 of SPEC §5: the reason reaches the summary face, and it is the same
    one the event stream carries."""
    ep = run_case("dev_c5", source=BlockedSource("holding obj_red_1 but no pending goal names it"),
                  source_kind="rule-like")

    assert ep.terminal_status == "failed"
    (event,) = ep.payloads("terminated_blocked")
    assert ep.result.termination_reason, "a blocked episode with a stated reason must say so"
    assert ep.result.termination_reason == event["reason"]
    assert ep.result.termination_reason == "holding obj_red_1 but no pending goal names it"
    # the reason lands on `blocked_reason`, the field the loop writes; a backend that
    # seals the episode in its own vocabulary keeps `termination_reason` for that
    assert ep.runtime.blocked_reason == ep.result.termination_reason
    assert ep.runtime.termination_reason is None, "this runtime has no sealed vocabulary"
    # the note the summary and `episode_end` carry is the same account, not the old
    # hard-coded string: the reader of a csv row sees what the reader of the event sees
    assert ep.result.artifacts["note"] == ep.result.termination_reason
    (end,) = [p for p in ep.payloads("episode_end")]
    assert end["note"] == ep.result.termination_reason


def test_a_blocked_episode_keeps_failure_type_none(run_case):
    """Acceptance 2: the fix is the reason field, not a new `FailureCode`. `blocked` is
    the model declining to act, which is not a frozen failure code, and v0.5 SPEC §2.2
    keeps the enum closed — the surface evidence of that decision is this assertion."""
    ep = run_case("dev_c5", source=BlockedSource("no feasible next action"), source_kind="rule-like")

    assert ep.failure_type is None
    assert ep.result.failure_type is None


def test_a_silent_block_still_states_a_reason(run_case):
    """Acceptance 1 read at its weakest: a decision with an empty rationale must not
    leave the summaries empty again. The fallback names the silence; it does not invent a
    cause, so nothing downstream can mistake it for one."""
    ep = run_case("dev_c5", source=BlockedSource(""), source_kind="rule-like")

    assert FALLBACK_REASON == "blocked by model", "the fallback names the silence, unchanged"
    assert ep.result.termination_reason == FALLBACK_REASON
    (event,) = ep.payloads("terminated_blocked")
    assert event["reason"] == FALLBACK_REASON
    assert ep.failure_type is None


def test_clarify_still_carries_its_failure_code(run_case):
    """Acceptance 3: the neighbouring control outcome does not move. `clarify` is the
    path that already had a reason on the summary face — it is the comparison that says
    R1 aligned `blocked` to an existing behaviour rather than inventing one."""
    ep = run_case("dev_c5", steps=[("clarify", "which of the two red blocks?")])

    assert ep.terminal_status == "needs_clarification"
    assert ep.failure_type == "AMBIGUOUS_TASK"
    assert ep.result.artifacts["note"] == "which of the two red blocks?"


def test_a_success_states_no_reason_at_all(run_case):
    """Acceptance 4: a field filled "to look complete" is a fabricated row. Success keeps
    `termination_reason` as the `None` it has always been."""
    ep = run_case("dev_c5", mode="B")

    assert ep.terminal_status == "success"
    assert ep.result.termination_reason is None
    assert ep.result.artifacts["note"] == ""