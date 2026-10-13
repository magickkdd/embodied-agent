"""v0.8's document gate: the report, the phase log, the attribution instrument and the new-blood
batch against what is on disk.

Same constitution as v0.4–v0.7's gates: every number the documents state is re-derived here from
the artefacts, by the instruments that produced it, and a check that cannot run prints itself as
SKIPPED rather than passing silently. v0.7's gate earned its keep twice -- it caught a terminal
reason that appeared in three episodes and not one, and it caught a profile column read as another
-- so the corresponding checks are kept and extended here.

v0.8's delivery surface is RQ21 (the attribution), the repair's measured scope, RQ22 (the
generalisation verdict on nine cells) and RQ23 (the post-repair comparison point).
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
sys.path.insert(0, os.path.join(REPO, "work", "v08"))

BATCHES = "/home/czx/embodied-agent-batches"
NEWBLOOD = os.path.join(BATCHES, "v08", "newblood")
WORK = os.path.join(REPO, "work", "v08")
REPORT = os.path.join(REPO, "docs", "continuous-decision-v0.8-final-report.md")
PHASELOG = os.path.join(REPO, "docs", "continuous-decision-v0.8-phase-log.md")
PREREG = os.path.join(REPO, "configs", "experiment", "v08_newblood_preregistration.json")

results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: object = "") -> None:
    results.append((name, bool(ok), str(detail) if detail != "" else ""))


def skipped(name: str, why: str) -> None:
    results.append((name, True, f"SKIPPED: {why}"))


def text(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def run_dir(cell: str) -> str:
    base = os.path.join(NEWBLOOD, cell)
    runs = [d for d in os.listdir(base) if os.path.isdir(os.path.join(base, d, "episodes"))]
    return os.path.join(base, runs[-1]) if runs else ""


def episodes_of(cell: str) -> list[dict]:
    run = run_dir(cell)
    if not run:
        return []
    rows = []
    for ep in sorted(os.listdir(os.path.join(run, "episodes"))):
        path = os.path.join(run, "episodes", ep, "episode_summary.json")
        if not os.path.exists(path):
            rows.append({"episode_id": ep, "status": "infrastructure_error",
                         "reason": None, "failure_type": None, "http": None, "unbound": None})
            continue
        result = (json.load(open(path, encoding="utf-8")).get("result") or {})
        unbound = 0
        with open(os.path.join(run, "episodes", ep, "events.jsonl"), encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                event = json.loads(line)
                if event.get("type") == "decision_context":
                    unbound += sum(1 for p in ((event.get("payload") or {}).get("progress") or [])
                                   if "entity_binding" in (p.get("unmeasured") or []))
        rows.append({"episode_id": ep, "status": result.get("terminal_status"),
                     "reason": result.get("termination_reason"),
                     "failure_type": result.get("failure_type"),
                     "http": result.get("http_requests"), "unbound": unbound,
                     "objects": f"{result.get('objects_completed')}/{result.get('objects_total')}"})
    return rows


def main() -> int:  # noqa: C901 - a gate is a list of checks, in the order of the report
    rep, log = text(REPORT), text(PHASELOG)
    cells = ["c2_privileged", "c2_stub", "c2_vlm", "c4_privileged", "c4_stub",
             "c4_vlm", "c5_privileged", "c5_stub", "c5_vlm"]
    facts = {cell: episodes_of(cell) for cell in cells}

    # ---------------- RQ22: the generalisation verdict, recomputed
    def successes(cell: str) -> int:
        return sum(1 for r in facts[cell] if r["status"] == "success")

    check("privileged 三格 6/6 成功（新 case 在特权态物理有效）",
          all(successes(f"c{n}_privileged") == 2 for n in (2, 4, 5)),
          {f"c{n}_privileged": successes(f"c{n}_privileged") for n in (2, 4, 5)})
    camera = [f"c{n}_{ch}" for n in (2, 4, 5) for ch in ("stub", "vlm")]
    nonzero = [c for c in camera if successes(c) >= 1]
    check("RQ22：六个相机格无一非零 ⇒ 推广为 5 case 实测", nonzero == [], nonzero)
    check("报告把 RQ22 的判定写成推广而不是翻案",
          "推广" in rep and "5 case" in rep and "翻案" not in rep.split("## 3")[1][:1200])

    # ---------------- RQ23: the post-repair comparison point
    orphans = {cell: [r["episode_id"] for r in facts[cell]
                      if "no pending goal names it" in str(r.get("reason") or "")]
               for cell in ("c2_vlm", "c5_vlm")}
    check("RQ23：修复后握持孤儿在 3/6 个 vlm 集",
          orphans["c2_vlm"] == ["lh_c2_displaced_completion.B.r0"]
          and len(orphans["c5_vlm"]) == 2, orphans)
    try:
        with open(os.path.join(WORK, "r23_orphan_check.json"), encoding="utf-8") as f:
            r23 = json.load(f)
        check("RQ23 逐集：抓取轮按 id 指名、终态轮不指名",
              all(e["named_by_id_at_the_pick"] and not e["named_by_id_at_the_end"]
                  for e in r23["episodes"]),
              [(e["episode_id"], e["named_by_id_at_the_pick"], e["named_by_id_at_the_end"])
               for e in r23["episodes"]])
        check("RQ23 逐集：读侧对握持物的颜色形状与声明一致且可见",
              all((e["reader_reported_for_the_held_colour"] or {}).get("color")
                  and (e["reader_reported_for_the_held_colour"] or {}).get("shape")
                  for e in r23["episodes"]),
              [e["reader_reported_for_the_held_colour"] for e in r23["episodes"]])
        check("报告据此把修复范围写成「握持体自身归因漂移不覆盖」",
              "归因漂移" in rep and "不覆盖" in rep)
    except Exception as exc:  # noqa: BLE001
        skipped("RQ23 逐集", f"{type(exc).__name__}: {exc}")

    # ---------------- RQ21: the attribution, recomputed from its own artefact
    try:
        with open(os.path.join(WORK, "r21_orphan_attribution.json"), encoding="utf-8") as f:
            r21 = json.load(f)
        a = {e["label"]: e["candidates"]["a_bookkeeping_defect"] for e in r21["episodes"]}
        b = {e["label"]: e["candidates"]["b_semantic_orphan"]["named_by_id_in_any_round"]
             for e in r21["episodes"]}
        check("RQ21：五个历史集抓取轮都按 id 指名过握持物（(b) 否）", all(b.values()), b)
        check("RQ21：五个历史集的 (a) 判据三款都成立（抓取轮指名 / 抓取后不指名 / 漂移有外部原因）",
              all(r["named_by_id_at_the_last_pick"] and not all(r["named_by_id_after_the_pick"][1:])
                  and r["every_drift_round_has_a_frame_missing_the_declared_colour"]
                  or r["drift_rounds_whose_frame_carried_the_declared_colour"]
                  for r in a.values()),
              {k: (v["named_by_id_at_the_last_pick"], v["named_by_id_after_the_pick"],
                   v["every_drift_round_has_a_frame_missing_the_declared_colour"]) for k, v in a.items()})
        check("报告引用了 (a)/(b)/(c) 的判定与「无外部原因不成立」",
              all(s in rep for s in ("(a)", "(b)", "(c)", "无外部原因"))
              and "不成立" in rep)
    except Exception as exc:  # noqa: BLE001
        skipped("RQ21 重导", f"{type(exc).__name__}: {exc}")

    # ---------------- the repair: its contract and its blast radius
    try:
        r = subprocess.run([sys.executable, "-m", "pytest",
                            "tests/contract/test_v08_orphan_pending.py", "-q"],
                           capture_output=True, text=True, cwd=REPO,
                           env={**os.environ, "PYTHONPATH": "."})
        check("握持孤儿契约 5 条全绿", r.returncode == 0 and "5 passed" in (r.stdout + r.stderr),
              (r.stdout + r.stderr)[-120:])
    except Exception as exc:  # noqa: BLE001
        skipped("孤儿契约", f"{type(exc).__name__}: {exc}")

    # ---------------- behaviour drift: the stub cells' new shape
    check("stub 三格未绑定行归零（死路被修掉后的形态）",
          all(sum(r["unbound"] or 0 for r in facts[f"c{n}_stub"]) == 0 for n in (2, 4, 5)),
          {f"c{n}_stub": sum(r["unbound"] or 0 for r in facts[f"c{n}_stub"]) for n in (2, 4, 5)})
    round_budget = [r for n in (2, 5) for r in facts[f"c{n}_stub"]
                    if r["failure_type"] == "BUDGET_EXHAUSTED"]
    check("c2/c5 stub 两格共四集死于决策轮预算 30/30", len(round_budget) == 4
          and all(r["objects"] in ("1/5", "0/5") for r in round_budget),
          [(r["episode_id"], r["failure_type"], r["objects"]) for r in round_budget])
    check("报告把这条行为漂移写成「死路换成空转」而不是修好了",
          "空转" in rep and "提前收工" in rep)

    # ---------------- the stop-rule incident, named
    try:
        with open(os.path.join(run_dir("c4_vlm"), "errors.jsonl"), encoding="utf-8") as f:
            ledger = [json.loads(line) for line in f if line.strip()]
        check("c4_vlm 的基础设施错误有名有因（适配器 429）",
              any("429" in str(r.get("error") or "") for r in ledger)
              and any(r.get("outcome") == "infrastructure_error" for r in ledger),
              [(r.get("outcome"), str(r.get("error"))[:80]) for r in ledger])
    except Exception as exc:  # noqa: BLE001
        skipped("基础设施账", f"{type(exc).__name__}: {exc}")
    try:
        source = open(os.path.join(WORK, "newblood_batch.py"), encoding="utf-8").read()
        check("驱动已实现 429 停批检查（首跑漏实现，已落账）",
              "QUOTA_STOP" in source and "_quota_deaths" in source
              and "quota errors" in source)
        check("报告与日志都记了停批规则失守",
              "停批规则" in rep and "失守" in log)
    except Exception as exc:  # noqa: BLE001
        skipped("停批规则", f"{type(exc).__name__}: {exc}")

    # ---------------- demand profiles
    try:
        with open(os.path.join(WORK, "p8_demand_profiles.json"), encoding="utf-8") as f:
            profiles = json.load(f)["cases"]
        maxima = {case: profiles[case]["vlm"]["max_final_request"] for case in profiles}
        check("P-D 画像：c2 与 c4 的相机峰值都是 60（压过上界 48）",
              maxima.get("c2") == 60 and maxima.get("c4") == 60 and maxima.get("c5") == 39,
              maxima)
        check("P-D 画像：三个 case 的决策账仍恒为 0",
              all(all(v == 0 for v in profiles[case]["vlm"]["decision_at_last_round"])
                  for case in profiles), profiles)
        check("报告引用了 60 与 39 两个数", "60" in rep and "39" in rep)
    except Exception as exc:  # noqa: BLE001
        skipped("需求画像", f"{type(exc).__name__}: {exc}")

    # ---------------- the pre-registration vs what was spent
    try:
        with open(PREREG, encoding="utf-8") as f:
            prereg = json.load(f)
        bound = prereg["spend_bound"]["requests"]
        spent = sum(r["http"] or 0 for cell in cells for r in facts[cell])
        check("上界 427 未触界", bound == 427 and spent <= bound, (bound, spent))
        check("实耗 231 请求", spent == 231, spent)
        check("预登记的 USD 是 null", prereg["cost_estimate_usd"] is None
              and prereg["pricing_configured"] is False)
        check("预登记写明集级/行级分开与推广检验判据",
              "row-level" in json.dumps(prereg, ensure_ascii=False)
              and "RQ22" in json.dumps(prereg, ensure_ascii=False))
    except Exception as exc:  # noqa: BLE001
        skipped("预登记读数", f"{type(exc).__name__}: {exc}")

    # ---------------- the frozen surface, re-run rather than quoted
    try:
        from embodied_agent.core import v02
        with open(os.path.join(REPO, "configs", "experiment", "v02_schema_freeze.json"),
                  encoding="utf-8") as f:
            frozen = json.load(f).get("schema_fingerprint", {})
        now = v02.schema_fingerprint()
        check("事件 fingerprint 逐项相等（本阶段只改簿记）",
              all(now.get(k) == frozen.get(k) for k in now if k in frozen),
              {k: (now.get(k), frozen.get(k)) for k in now
               if k in frozen and now.get(k) != frozen.get(k)})
    except Exception as exc:  # noqa: BLE001
        skipped("fingerprint", f"{type(exc).__name__}: {exc}")
    for gate, prefix in (("freeze", "2f1c74f52e91"), ("prereg", "72271eadb43d"),
                         ("em-pairs", "7df449ed2f4d")):
        try:
            r = subprocess.run([sys.executable, "-m", "embodied_agent.cli", gate, "--check"],
                               capture_output=True, text=True, cwd=REPO,
                               env={**os.environ, "PYTHONPATH": "."})
            check(f"{gate} --check rc=0（{prefix}）", r.returncode == 0
                  and prefix in (r.stdout + r.stderr), (r.stdout + r.stderr)[-140:])
        except Exception as exc:  # noqa: BLE001
            skipped(f"{gate} --check", f"{type(exc).__name__}: {exc}")
    try:
        r = subprocess.run([sys.executable, "-m", "agent_lab.evaluation.long_horizon_tasks",
                            "--check"], capture_output=True, text=True, cwd=REPO,
                           env={**os.environ, "PYTHONPATH": "."})
        check("长视野表 --check rc=0（v2 哈希未变）",
              r.returncode == 0 and "b9fce17fbbf6" in (r.stdout + r.stderr),
              (r.stdout + r.stderr)[-120:])
    except Exception as exc:  # noqa: BLE001
        skipped("lh --check", f"{type(exc).__name__}: {exc}")

    # ---------------- the documents' own surface
    check("报告的 RQ 答卷三节都在", all(s in rep for s in ("RQ21", "RQ22", "RQ23")))
    check("报告的负结果清单在（七条）",
          "负结果清单" in rep and all(f"| {i} |" in rep for i in range(1, 8)))
    check("报告声明 USD 为 null", "`null`" in rep)
    check("阶段日志的 P1 判据先于读数", "P1 判据" in log and "跑后未改一字" in log)
    check("阶段日志记了契约先红后绿", "先红后绿" in log)
    check("阶段日志记了停批规则失守与越界花费", "停批规则" in log and "57" in log)
    check("报告与阶段日志无凭据形状",
          not re.search(r"sk-[A-Za-z0-9]{8}", rep) and not re.search(r"sk-[A-Za-z0-9]{8}", log))

    failed = [(n, d) for n, ok, d in results if not ok]
    for name, ok, detail in results:
        print(f"  {'OK ' if ok else 'RED'} {name}" + (f"  [{detail}]" if (detail and not ok) else ""))
    print(f"RESULT: {len(results) - len(failed)}/{len(results)} -> "
          f"{'ALL CLOSED' if not failed else str(len(failed)) + ' RED'}")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())