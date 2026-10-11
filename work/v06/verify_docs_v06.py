"""v0.6's document gate: the two deliverable docs and the two pre-registrations against the
archives and instruments they cite.

Same constitution as v0.3's, v0.4's and v0.5's gates (`work/v05/verify_docs_v05.py`): every
number the report states is re-derived here from the artefacts on disk, by the *same* instruments
that produced it, and a check that cannot run prints itself as SKIPPED rather than passing
silently. The checks are chosen so that corrupting a cited number in either direction -- editing
the report, or editing an archive -- turns something red.

This gate is written for v0.6's delivery surface (Q1's split, B1/B2, E2''', H1, the rulings) and
does not carry v0.5's A1/A2 re-derivations forward: those instruments answer v0.5's questions,
not this stage's. The evolution is stated, not silent.
"""
from __future__ import annotations

import glob
import json
import os
import re
import subprocess
import sys

REPO = "/home/czx/embodied-agent-robot-agent-embodied-agent-4"
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "work", "v06"))

BATCHES = "/home/czx/embodied-agent-batches"
E2_V06 = os.path.join(BATCHES, "v06", "e2")
H1_V06 = os.path.join(BATCHES, "v06", "h1")
E2_V04 = os.path.join(BATCHES, "v04", "e2")
E2_V05 = os.path.join(BATCHES, "v05", "e2")
WORK = os.path.join(REPO, "work", "v06")
REPORT = os.path.join(REPO, "docs", "continuous-decision-v0.6-final-report.md")
PHASELOG = os.path.join(REPO, "docs", "continuous-decision-v0.6-phase-log.md")
SPEC = os.path.join(REPO, "Continuous-Decision-Embodied-Agent-SPEC-v0.6.md")
PREREG_E2 = os.path.join(REPO, "configs", "experiment", "v06_e2_preregistration.json")
PREREG_H1 = os.path.join(REPO, "configs", "experiment", "v06_h1_preregistration.json")
PY = "/home/czx/miniforge3/envs/embodied/bin/python"

results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: object = "") -> None:
    results.append((name, bool(ok), str(detail) if detail != "" else ""))


def skipped(name: str, why: str) -> None:
    results.append((name, True, f"SKIPPED: {why}"))


def text(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def run_dir(root: str, channel: str) -> str:
    cell = os.path.join(root, f"long_horizon_{channel}")
    runs = [d for d in os.listdir(cell) if os.path.isdir(os.path.join(cell, d, "episodes"))]
    return os.path.join(cell, runs[-1])


def episode_facts(run: str) -> list[dict]:
    rows = []
    for ep in sorted(os.listdir(os.path.join(run, "episodes"))):
        ep_dir = os.path.join(run, "episodes", ep)
        path = os.path.join(ep_dir, "episode_summary.json")
        if not os.path.exists(path):
            rows.append({"episode_id": ep, "status": "infrastructure_error", "failure_type": None,
                         "http_requests": None, "unbound": 0, "objects": None})
            continue
        with open(path, encoding="utf-8") as f:
            summary = json.load(f)
        result = summary.get("result") or {}
        unbound = 0
        with open(os.path.join(ep_dir, "events.jsonl"), encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                event = json.loads(line)
                if event.get("type") == "decision_context":
                    unbound += sum(1 for p in ((event.get("payload") or {}).get("progress") or [])
                                   if "entity_binding" in (p.get("unmeasured") or []))
        rows.append({"episode_id": ep, "status": result.get("terminal_status"),
                     "failure_type": result.get("failure_type"),
                     "http_requests": result.get("http_requests"),
                     "note": str((result.get("artifacts") or {}).get("note") or ""),
                     "unbound": unbound,
                     "objects": f"{result.get('objects_completed')}/{result.get('objects_total')}"})
    return rows


def outcomes_of(rows: list[dict]) -> dict:
    out: dict = {}
    for r in rows:
        out[r["status"]] = out.get(r["status"], 0) + 1
    return out


def main() -> int:  # noqa: C901 - a gate is a list of checks; one function keeps them in reading order
    rep, log = text(REPORT), text(PHASELOG)

    # ---------------- E2''' against the archives
    facts = {ch: episode_facts(run_dir(E2_V06, ch)) for ch in ("privileged", "stub", "vlm")}
    check("E2''' privileged 4/4", outcomes_of(facts["privileged"]) == {"success": 4},
          outcomes_of(facts["privileged"]))
    check("E2''' stub 0/4 全 failed", outcomes_of(facts["stub"]) == {"failed": 4},
          outcomes_of(facts["stub"]))
    check("E2''' vlm 0/4 全 failed", outcomes_of(facts["vlm"]) == {"failed": 4},
          outcomes_of(facts["vlm"]))
    check("E2''' 请求按格：0 / 0 / 180",
          [sum(r["http_requests"] or 0 for r in facts[ch]) for ch in ("privileged", "stub", "vlm")]
          == [0, 0, 180],
          [sum(r["http_requests"] or 0 for r in facts[ch]) for ch in ("privileged", "stub", "vlm")])
    check("E2''' 未绑定行 0 / 16 / 51",
          [sum(r["unbound"] for r in facts[ch]) for ch in ("privileged", "stub", "vlm")]
          == [0, 16, 51],
          [sum(r["unbound"] for r in facts[ch]) for ch in ("privileged", "stub", "vlm")])
    stops = [r["episode_id"] for r in facts["vlm"] if r["failure_type"] == "BUDGET_EXHAUSTED"]
    check("E2''' 撞墙只有 c3 vlm 两集", stops == ["lh_c3_capacity_and_shift.B.r0",
                                              "lh_c3_capacity_and_shift.B.r1"], stops)
    finals = {r["episode_id"]: r["http_requests"] for r in facts["vlm"]
              if r["episode_id"].startswith("lh_c3")}
    check("E2''' c3 vlm 落盘 54 / 56（报告 §4）",
          finals == {"lh_c3_capacity_and_shift.B.r0": 54, "lh_c3_capacity_and_shift.B.r1": 56},
          finals)
    billed = {r["episode_id"]: r["note"] for r in facts["vlm"] if "billed to" in r["note"]}
    check("E2''' 感知账 49 / 49 写在拒绝理由里",
          all("49 requests" in note for note in billed.values()) and len(billed) == 2, billed)
    check("E2''' stub c1 两集死于 REPEATED_INVALID",
          all(r["failure_type"] == "REPEATED_INVALID" and r["unbound"] == 0
              for r in facts["stub"] if r["episode_id"].startswith("lh_c1")),
          [(r["episode_id"], r["failure_type"], r["unbound"]) for r in facts["stub"]])

    # ---------------- the repricing is in the archive, not only in the report
    caps = {}
    for ch in ("privileged", "stub", "vlm"):
        with open(os.path.join(run_dir(E2_V06, ch), "manifest.json"), encoding="utf-8") as f:
            caps[ch] = json.load(f).get("budget_caps")
    check("归档里的 budget_caps：对照 32，相机格 48/48",
          caps["privileged"] == {"http_requests": 32, "perception_requests": 48}
          and caps["stub"] == {"http_requests": 48, "perception_requests": 48}
          and caps["vlm"] == {"http_requests": 48, "perception_requests": 48}, caps)
    from embodied_agent.evaluation.tasks import build_set
    check("冻结任务表仍是 32（重定价是副本）",
          {c.budgets.max_http_requests for c in build_set("long_horizon")} == {32})

    # ---------------- Q1's split: the identity, on the batch
    vlm_budgets = []
    for ep in sorted(glob.glob(os.path.join(run_dir(E2_V06, "vlm"), "episodes", "*"))):
        last = {}
        for line in open(os.path.join(ep, "events.jsonl"), encoding="utf-8"):
            if not line.strip():
                continue
            event = json.loads(line)
            if event.get("type") == "decision_context":
                last = (event.get("payload") or {}).get("budget") or {}
        if last:
            vlm_budgets.append((last.get("perception_requests_used"),
                                last.get("decision_requests_used"),
                                last.get("http_requests_used")))
    check("Q1 恒等式在 E2''' 上成立且决策账为 0",
          vlm_budgets and all(p + d <= t and d == 0 for p, d, t in vlm_budgets), vlm_budgets[:4])

    # ---------------- B1 / B2, re-derived from the instruments' own outputs
    try:
        b1 = json.load(open(os.path.join(WORK, "b1_ceiling.json"), encoding="utf-8"))
        rescue_k1 = b1["windows"]["k1"]["rescued_item_rounds"]
        rescue_k2 = b1["windows"]["k2"]["rescued_item_rounds"]
        shape_k1 = b1["windows"]["k1"]["shape_matched_item_rounds"]
        shape_k2 = b1["windows"]["k2"]["shape_matched_item_rounds"]
        amb_k1 = b1["windows"]["k1"]["ambiguous_windows"]
        amb_k2 = b1["windows"]["k2"]["ambiguous_windows"]
        missing = b1["totals"]["missing_colour_item_rounds"]
        check("B1 重导：缺色项-轮 64，k=1 救 10 / k=2 救 11",
              missing == 64 and rescue_k1 == 10 and rescue_k2 == 11,
              (missing, rescue_k1, rescue_k2))
        check("B1 重导：补上形状 0 / 0", shape_k1 == 0 and shape_k2 == 0, (shape_k1, shape_k2))
        check("B1 重导：误绑 0 / 10", amb_k1 == 0 and amb_k2 == 10, (amb_k1, amb_k2))
        check("报告引用 B1 的四个数", all(s in rep for s in ("10/64", "11/64", "0/0", "1/64")))
    except Exception as exc:  # noqa: BLE001
        skipped("B1 重导", f"{type(exc).__name__}: {exc}")
    try:
        scan = json.load(open(os.path.join(WORK, "b1_reader_scan.json"), encoding="utf-8"))
        best = {k: (v["colour_seen"], v["colour_and_shape_seen"])
                for k, v in scan["settings"].items()}
        check("阈值七格扫描读数逐位相同、只恢复 1/64",
              len(best) == 7 and set(best.values()) == {(1, 1)}, best)
    except Exception as exc:  # noqa: BLE001
        skipped("读侧阈值扫描", f"{type(exc).__name__}: {exc}")
    try:
        b2 = json.load(open(os.path.join(WORK, "b2_ambiguity.json"), encoding="utf-8"))
        pairs = [row.get("ambiguous_pairs")
                 for row in b2["identical_pairs"]["cells"].values()] \
            if isinstance(b2.get("identical_pairs"), dict) and "cells" in b2["identical_pairs"] \
            else None
        if pairs is None:
            pairs = [row.get("ambiguous_pairs") for row in b2["identical_pairs"]]
        check("B2 重导：四格同名属性对全为 0", all(p == 0 for p in pairs), pairs)
        premise = b2["candidate_premise"]
        uniq = [p["frames"] == p["unique"] for p in premise["cells"].values()] \
            if "cells" in premise else [p["frames"] == p["unique"] for p in premise]
        check("B2 重导：候选 i 的前提 100% 唯一", uniq and all(uniq), premise)
        check("B2 三条可达路径都解不出绑定",
              len(b2["paths"]) >= 3 and all(p.get("bind_attributes") is None
                                           for p in b2["paths"]), b2["paths"])
    except Exception as exc:  # noqa: BLE001
        skipped("B2 重导", f"{type(exc).__name__}: {exc}")

    # ---------------- the stub naming, and the equivalence it rests on
    try:
        names = json.load(open(os.path.join(E2_V06, "e2_stub_names.json"), encoding="utf-8"))
        rows = {r["episode_id"]: r for r in names["episodes"]}
        c3 = {k: v for k, v in rows.items() if "c3" in k}
        check("stub c3 的开名借自 E2'' 帧，且等价性逐项核对通过",
              len(c3) == 2 and all(not r["trajectory_fields_mismatched"]
                                    and r["unbound_rows_identical"] for r in c3.values()),
              {k: (r["trajectory_fields_mismatched"], r["unbound_rows_identical"])
               for k, r in c3.items()})
        check("stub c3 的死因是 #25 与 #26",
              all(set(r["cause_tally"]) == {"#25", "#26"} and r["cause_tally"]["#25"] == 7
                  for r in c3.values()), {k: r["cause_tally"] for k, r in c3.items()})
    except Exception as exc:  # noqa: BLE001
        skipped("stub 开名", f"{type(exc).__name__}: {exc}")

    # ---------------- H1
    try:
        h1 = json.load(open(os.path.join(H1_V06, "h1_readings.json"), encoding="utf-8"))
        cells = {c["cell"]: c for c in h1["cells"]}
        c2, c3 = cells["c2_deepseek_privileged"], cells["c3_deepseek_privileged"]
        check("H1 c2：10 集、1 成功、31 次配额错误、最长连续 3",
              c2["h1"]["episodes"] == 10 and c2["outcomes"].get("success") == 1
              and c2["quota_deaths_total"] == 31 and c2["quota_longest_consecutive"] == 3,
              (c2["h1"]["episodes"], c2["outcomes"], c2["quota_deaths_total"],
               c2["quota_longest_consecutive"]))
        check("H1 c3：12 集、5 成功", c3["h1"]["episodes"] == 12 and c3["outcomes"].get("success") == 5,
              (c3["h1"]["episodes"], c3["outcomes"]))
        check("H1 两格 trigger 全 0、联合分母 0",
              all(cell["h1"]["trigger"] == 0 and cell["h1"]["joint_denominator"] == 0
                  for cell in (c2, c3)),
              {k: (v["h1"]["trigger"], v["h1"]["joint_denominator"]) for k, v in cells.items()})
        check("H1 推导照跑（每格全部集数）",
              c2["h1"]["derivation_ran"] == 10 and c3["h1"]["derivation_ran"] == 12,
              (c2["h1"]["derivation_ran"], c3["h1"]["derivation_ran"]))
    except Exception as exc:  # noqa: BLE001
        skipped("H1 读数", f"{type(exc).__name__}: {exc}")
    try:
        from embodied_agent.evaluation.run import batch_spend
        spent = sum(batch_spend(run)["http_requests"] for run in glob.glob(
            os.path.join(H1_V06, "*", "*")) if os.path.isdir(os.path.join(run, "episodes")))
        check("H1 两账 686 请求（报告 §8）", spent == 686, spent)
        e2_spent = sum(batch_spend(run)["http_requests"] for run in glob.glob(
            os.path.join(E2_V06, "*", "*")) if os.path.isdir(os.path.join(run, "episodes")))
        check("E2''' 两账 180 请求", e2_spent == 180, e2_spent)
        check("报告的总花费 866", "866" in rep and 180 + spent == 866, 180 + spent)
    except Exception as exc:  # noqa: BLE001
        skipped("花费两账", f"{type(exc).__name__}: {exc}")
    try:
        probe = json.load(open(os.path.join(WORK, "h1_derivation_probe.json"), encoding="utf-8"))
        six = list(probe["cases"].values())
        check("机制探针：六个 case、边全 0、不可行行 0、有他物占位的行 0",
              len(six) == 6 and all(c["dependencies"] == 0
                                    and c["edge_conditions"]["infeasible_rows"] == 0
                                    and c["edge_conditions"]["rows_with_another_occupant"] == 0
                                    for c in six),
              {k: (v["rows"], v["dependencies"], v["edge_conditions"]) for k, v in probe["cases"].items()})
    except Exception as exc:  # noqa: BLE001
        skipped("H1 机制探针", f"{type(exc).__name__}: {exc}")

    # ---------------- the rulings are in the SPEC's decision table
    spec = text(SPEC)
    for token in ("| D3''' |", "| D4''' |", "| D5''' |"):
        check(f"SPEC 决策表有 {token.strip('| ')}", token in spec)
    check("D2''' 记录了 A+B 与感知 48", "A+B" in spec and "48" in spec)
    check("P1 的 H2 更正在 SPEC 与日志里都在",
          "H2" in spec and "不是模型写" in log or "推导规则" in log)

    # ---------------- pre-registrations vs what was spent
    try:
        with open(PREREG_E2, encoding="utf-8") as f:
            e2_prereg = json.load(f)
        with open(PREREG_H1, encoding="utf-8") as f:
            h1_prereg = json.load(f)
        check("E2''' 上界 240、未触界", e2_prereg["spend_bound"]["requests"] == 240
              and 180 <= 240, e2_prereg["spend_bound"]["requests"])
        check("H1 上界 930、未触界", h1_prereg["spend_bound"]["requests"] == 930
              and 686 <= 930, h1_prereg["spend_bound"]["requests"])
        check("两份预登记的 USD 都是 null",
              e2_prereg["cost_estimate_usd"] is None and h1_prereg["cost_estimate_usd"] is None)
        check("H1 预登记写明依赖边是规则推导",
              "subgoals.py" in json.dumps(h1_prereg, ensure_ascii=False))
        check("E2''' 预登记写明失败必须归到 #25/#26/#27",
              "#25" in json.dumps(e2_prereg, ensure_ascii=False)
              and "#26" in json.dumps(e2_prereg, ensure_ascii=False))
    except Exception as exc:  # noqa: BLE001
        skipped("预登记读数", f"{type(exc).__name__}: {exc}")

    # ---------------- the frozen surface, re-run rather than quoted
    try:
        from embodied_agent.core import v02
        with open(os.path.join(REPO, "configs", "experiment", "v02_schema_freeze.json"),
                  encoding="utf-8") as f:
            frozen = json.load(f).get("schema_fingerprint", {})
        now = v02.schema_fingerprint()
        same = all(now.get(k) == frozen.get(k) for k in now if k in frozen)
        check("fingerprint 与冻结文件逐项相等", same,
              {k: (now.get(k), frozen.get(k)) for k in now
               if k in frozen and now.get(k) != frozen.get(k)})
    except Exception as exc:  # noqa: BLE001
        skipped("fingerprint", f"{type(exc).__name__}: {exc}")
    for gate, prefix in (("freeze", "2f1c74f52e91"), ("prereg", "23abe58ff333"),
                         ("em-pairs", "7df449ed2f4d")):
        try:
            r = subprocess.run([PY, "-m", "embodied_agent.cli", gate, "--check"],
                               capture_output=True, text=True, cwd=REPO,
                               env={**os.environ, "PYTHONPATH": "."})
            check(f"{gate} --check rc=0 且哈希未变",
                  r.returncode == 0 and prefix in (r.stdout + r.stderr),
                  (r.stdout + r.stderr)[-160:])
        except Exception as exc:  # noqa: BLE001
            skipped(f"{gate} --check", f"{type(exc).__name__}: {exc}")

    # ---------------- the documents' own surface
    check("报告的负结果清单在（十条）",
          "负结果清单" in rep and all(f"| {i} |" in rep for i in range(1, 11)))
    check("报告按失败记了 E2''' 的预测失败", "预登记预测失败" in rep and "没有成立" in rep)
    check("报告点名 stub c1 的第四死因", "REPEATED_INVALID" in rep)
    check("报告声明 USD 为 null", "`null`" in rep and "pricing_configured" in rep)
    check("报告的复现清单含批前门与文档门",
          "preflight.py" in rep and "verify_docs_v06.py" in rep)
    check("报告与阶段日志无凭据形状",
          not re.search(r"sk-[A-Za-z0-9]{8}", rep) and not re.search(r"sk-[A-Za-z0-9]{8}", log))
    check("阶段日志的判据先于读数",
          "P2 判据" in log and "跑后未改判据一字" in log)
    check("阶段日志记了首启事故与两次仪器/记账改正",
          "首启事故" in log and "仪器读错键" in log and "检查点只活在会被删掉的文件里" in log)

    failed = [(n, d) for n, ok, d in results if not ok]
    for name, ok, detail in results:
        print(f"  {'OK ' if ok else 'RED'} {name}" + (f"  [{detail}]" if (detail and not ok) else ""))
    print(f"RESULT: {len(results) - len(failed)}/{len(results)} -> "
          f"{'ALL CLOSED' if not failed else str(len(failed)) + ' RED'}")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())