"""The single-repo zone split: the agent body never imports the apparatus.

v0.8 P0 moved `evaluation/`, `benchmark/` and `benchmark_mujoco/` out of the
`embodied_agent` package into the sibling `agent_lab` package. The dependency
direction is one-way — agent_lab depends on embodied_agent — and two failure
modes are pinned here permanently:

1. a body subpackage importing `agent_lab` (inverts the layering);
2. a parent-relative import (`from ..`) anywhere inside agent_lab: before the
   move, `from ..core.x` inside evaluation resolved to `embodied_agent.core`;
   after the move the same line would silently resolve to `agent_lab.core`.
   Relative-to-parent inside agent_lab is therefore banned outright.
`embodied_agent/cli.py` is the exempt entry dispatcher: its gate commands
(`freeze --check`, `prereg --check`, `em-pairs --check`, batch drivers) reach
the apparatus through function-level imports, and the documented command
surface `python -m embodied_agent.cli ...` survives the split unchanged.
"""
from __future__ import annotations

import ast
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_AGENT = _REPO / "embodied_agent"
_LAB = _REPO / "agent_lab"

#: the body subpackages that stayed inside `embodied_agent`
BODY_SUBPACKAGES = ("core", "perception", "planning", "adapters",
                    "acquisition", "episodic")


#: the declared exceptions — the only body→lab imports allowed, each a lazy
#: function-level site that predates the split (the migration surfaced them,
#: it did not create them). The apparatus owns the frozen task-table
#: primitives (`evaluation.tasks`, `evaluation.calibration`); until those
#: primitives move into the body, these two call-sites reach across the zone.
DECLARED_CROSS_ZONE = {
    ("perception", "arm.py", "agent_lab.evaluation"),
    ("acquisition", "sandbox.py", "agent_lab.evaluation"),
}


def _py_files(root: Path):
    for path in root.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        yield path


def _cross_zone_sites(tree) -> set[tuple[str, str, str]]:
    """(subpackage, file, lab_root_module) for every agent_lab import in a tree."""
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "agent_lab" or alias.name.startswith("agent_lab."):
                    found.add(alias.name.split(".")[1])
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            mod = node.module or ""
            if mod == "agent_lab" or mod.startswith("agent_lab."):
                found.add(mod.split(".")[1])
    return found


def test_body_cross_zone_imports_equal_the_declared_set():
    """No body→lab import beyond the declared exceptions — and none of the
    declared exceptions silently removed (set equality, both directions)."""
    offenders = set()
    for sub in BODY_SUBPACKAGES:
        for path in _py_files(_AGENT / sub):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for root_mod in _cross_zone_sites(tree):
                offenders.add((sub, path.name, f"agent_lab.{root_mod}"))
    undeclared = offenders - DECLARED_CROSS_ZONE
    missing = DECLARED_CROSS_ZONE - offenders
    assert not undeclared, ("body→lab import outside the declared exception "
                            "list:\n" + "\n".join(map(str, sorted(undeclared))))
    assert not missing, ("a declared cross-zone site disappeared — update "
                         "DECLARED_CROSS_ZONE:\n" + "\n".join(map(str, sorted(missing))))


def test_agent_lab_has_no_parent_relative_imports():
    offenders = []
    for path in _py_files(_LAB):
        for line_no, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith("from .."):
                offenders.append(f"{path.relative_to(_REPO)}:{line_no}")
    assert not offenders, ("parent-relative imports inside agent_lab resolve "
                           "against agent_lab, not embodied_agent — the exact "
                           "silent-misimport the v0.8 migration had to avoid:\n"
                           + "\n".join(offenders))


def test_agent_lab_still_depends_on_the_body():
    run_py = _LAB / "evaluation" / "run.py"
    assert run_py.exists(), "the apparatus lost its scoring harness?"
    assert "from embodied_agent.core" in run_py.read_text(encoding="utf-8"), \
        "agent_lab must keep its one-way dependency on the agent body"


def test_body_top_level_modules_are_clean_too():
    offenders = []
    for path in _AGENT.glob("*.py"):
        if path.name == "cli.py":  # the exempt entry dispatcher
            continue
        for root_mod in sorted(_cross_zone_sites(ast.parse(
                path.read_text(encoding="utf-8")))):
            offenders.append(f"{path.relative_to(_REPO)} agent_lab.{root_mod}")
    assert not offenders, "\n".join(offenders)
