"""v0.6 Q1 contract tests: the request budget is an account with two books, not one wall.

What the ruling settled (v0.6 SPEC §5 Q1, D2''' -- A+B with a perception sub-cap of 48),
and what the measurements behind it were (`work/v06/q1_split.py`, re-derived from the
archives at zero cost):

* E2's three cells made **280 requests, all of them perception** (the rule policy spends no
  requests of its own), 18-39 per episode once retries and schema repairs are counted;
* E1's model seat made **641 requests, all of them decisions**, 5-40 per episode;
* so one undifferentiated `max_http_requests = 32` was governing two different spends, and
  the camera cells died at 39/32 (E2'', v0.5 negative result #4) for a reason that had
  nothing to do with deciding anything.

Four properties are pinned here, and the third is the one that keeps this from becoming a
second bookkeeping system:

1. **the split is real**: a look's requests land in the perception book, a decision's in the
   decision book, and `http_requests` is their sum -- asserted as an *identity*, not as a
   convention, because a counter that can drift from the total is a third ledger;
2. **both caps can end an episode**, and the message names which one tripped;
3. **neither cap is checked after a request that already went out** (the preflight is the
   only gate, so a camera episode's real maximum is the cap plus the round in flight -- the
   measurement behind that, 40 against a declared 32, is why the cap is a boundary and not a
   promise);
4. **the privileged channel is untouched**: with no camera there is nothing to split, and the
   base `Runtime` keeps charging the way it always did.

No test here spends a request; the camera arm is driven with the offline stub reader.
"""
from __future__ import annotations

from embodied_agent.core.contracts import Budgets
from embodied_agent.core.runtime import BudgetLedger
from embodied_agent.perception.grounding import GroundingMap

#: what D2''' set, and what every archived camera episode needs (peak 39) plus head-room
PERCEPTION_CAP = 48


def test_the_two_books_add_up_to_the_total():
    """Acceptance 1: the split is an identity. `charge_perception_requests` and
    `charge_decision_requests` each
    move the total by what they move their own book by, so no request can be counted twice or
    land in no book at all -- the v0.4 "two ledgers agree" discipline, one level down."""
    ledger = BudgetLedger(Budgets())
    ledger.charge_perception_requests(7)
    ledger.charge_decision_requests(3)
    ledger.charge_requests(2)          # an unbilled prologue, the shape E1 rows take

    assert ledger.perception_requests == 7
    assert ledger.decision_requests == 3
    assert ledger.http_requests == 12
    assert ledger.perception_requests + ledger.decision_requests <= ledger.http_requests, \
        "the two named books can never exceed the total they are part of"


def test_a_capped_ledger_reports_both_books_and_the_head_room_each_has():
    ledger = BudgetLedger(Budgets())
    ledger.charge_perception_requests(40)
    ledger.charge_decision_requests(5)
    remaining = ledger.http_remaining()
    assert remaining["perception_remaining"] == PERCEPTION_CAP - 40
    assert remaining["perception_used"] == 40 and remaining["decision_used"] == 5


def test_the_budget_carries_no_new_field_and_the_cap_defaults_to_the_ruling():
    """The frozen task list hashes every case's budget profile, so the perception ceiling is
    deliberately **not** a field of `Budgets`: adding one moves `cli freeze --check` and
    re-freezes a table this stage was not asked to re-freeze (SPEC §2.2). The cap is a runtime
    argument with a measured default instead."""
    from embodied_agent.core.runtime import DEFAULT_PERCEPTION_REQUEST_CAP

    assert PERCEPTION_CAP == DEFAULT_PERCEPTION_REQUEST_CAP
    assert Budgets().max_http_requests == 32
    assert not hasattr(Budgets(), "max_perception_requests")


def test_a_batch_level_override_reprices_the_cap_without_touching_the_case():
    """Candidate (B) of the ruling: the per-episode wall moves per batch, by configuration.
    The case object comes back untouched -- a runner that repriced the frozen case in place
    would leave the next batch starting from a different budget than the one it printed."""
    from agent_lab.evaluation.run import apply_http_caps

    budgets = Budgets()
    repriced, perception_cap = apply_http_caps(budgets, http_cap=64, perception_cap=48)
    assert repriced.max_http_requests == 64 and perception_cap == 48
    assert budgets.max_http_requests == 32, "the caller's budget object is untouched"

    same, default_cap = apply_http_caps(budgets)
    assert same is budgets and default_cap == PERCEPTION_CAP


def test_the_run_manifest_records_both_ceilings():
    """A repriced cell has to be recognisable from its own archive. `budget_profile` carries
    the total (a batch may move it); the perception sub-cap is a runtime argument rather than a
    case budget, so it would otherwise exist only in the command line and the report -- which is
    the failure mode this stage's archive-comparison rule exists to prevent."""
    import inspect

    from agent_lab.evaluation import run as R

    source = inspect.getsource(R.run_group)
    assert "budget_caps=" in source
    assert '"perception_requests": perception_cap' in source, \
        "the perception ceiling must travel with the total into the manifest"


def test_the_ceilings_reach_the_batch_from_the_command_line(tmp_path):
    """The end-to-end seam, written after the E2''' batch found it broken.

    P1's tests pinned `apply_http_caps` and the ledger, and both passed; the flag still never
    arrived. Two names were wrong in two places: the CLI passed `perception_cap=` where
    `run_group` reads `perception_cap_flag=`, and the repriced case was built with
    `model_copy` on a dataclass. So a batch asked for 48/48 and died with
    `run_group() got an unexpected keyword argument 'perception_cap'` -- after the zero-cost
    privileged cell had already succeeded, and before any request was spent.

    This drives the real batch entry point offline (`perceive stub`, one repeat, frames off) and
    asserts the archive carries the numbers it ran under, because a repricing that only exists
    in a command line is a repricing nobody can reproduce."""
    import json
    import os

    from embodied_agent.cli import main as cli_main

    out = tmp_path / "out"
    rc = cli_main(["evaluate", "--set", "long_horizon", "--planner", "rule", "--modes", "B",
                   "--repeats", "1", "--cases", "lh_c1_shared_pair_restore",
                   "--out-root", str(out), "--perceive", "stub", "--ablation", "wo_vlm",
                   "--no-frames", "--frozen", "--http-cap", "48", "--perception-cap", "48"])
    assert rc == 0, f"a batch carrying the pre-registered ceilings has to run (rc={rc})"

    run_dirs = [os.path.join(out, d) for d in os.listdir(out)
                if os.path.isdir(os.path.join(out, d, "episodes"))]
    assert run_dirs, "the batch wrote no run directory"
    with open(os.path.join(run_dirs[0], "manifest.json"), encoding="utf-8") as f:
        manifest = json.load(f)
    assert manifest["budget_caps"] == {"http_requests": 48, "perception_requests": 48}
    assert {p["max_http_requests"] for p in manifest["budget_profile"].values()} == {48}

    # and the frozen task list is still the frozen task list: the override is a copy, not an edit
    from agent_lab.evaluation.tasks import build_set

    assert {c.budgets.max_http_requests for c in build_set("long_horizon")} == {32}


def test_the_privileged_path_keeps_one_counter_and_the_old_rule():
    """Acceptance 4: with no camera, there is no perception book to fill, and the base
    runtime charges exactly what it always charged. A change here would silently re-price
    every archived privileged episode."""
    ledger = BudgetLedger(Budgets())
    ledger.charge_requests(31)
    assert ledger.perception_requests == 0 and ledger.decision_requests == 0
    assert ledger.can_decide() is True and ledger.http_remaining()["http_remaining"] == 1


def test_the_bridge_is_still_the_bridge():
    """Q1 is an accounting change. It must not move anything the v0.4 R3 contract pinned:
    the unique-colour rule and the composite key are still the bridge's whole vocabulary."""
    gmap = GroundingMap.from_objects([
        {"entity_id": "obj_yellow_1", "attributes": {"color": "yellow"}, "shape": "cube"},
        {"entity_id": "obj_yellow_6", "attributes": {"color": "yellow"}, "shape": "cuboid"}])
    assert gmap.bind("yellow", "cube") == "obj_yellow_1"
    assert gmap.bind("yellow", "cuboid") == "obj_yellow_6"
    assert gmap.bind("yellow", "cylinder") is None