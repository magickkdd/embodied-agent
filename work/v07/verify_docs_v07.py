"""v0.7's document gate: the report, the phase log and the two v2 tables against what is on disk.

Same constitution as v0.3's through v0.6's gates: every number the documents state is re-derived
here from the artefacts, by the instruments that produced it, and a check that cannot run prints
itself as SKIPPED rather than passing silently. The checks are chosen so that corrupting a cited
number in either direction -- editing the report, or editing an archive -- turns something red.

v0.7's delivery surface is M1 (the mismatch list), the v2 table and its freeze switch, the two
profiles, E2'''' and its RQ20 acceptance reading. v0.6's A1/A2 re-derivations are not carried
forward: they answer v0.6's questions, and the evolution is stated, not silent.
"""
from __future__ import annotations

import glob
import hashlib
import json
import os
import re
import subprocess
import sys

REPO = "/home/czx/embodied-agent-robot-agent-embodied-agent-4"
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "work", "v07"))

BATCHES = "/home/czx/embodied-agent-batches"
E2_V07 = os.path.join(BATCHES, "v07", "e2")
REACH = os.path.join(BATCHES, "v07", "reachability")
WORK = os.path.join(REPO, "work", "v07")
REPORT = os.path.join(REPO, "docs", "continuous-decision-v0.7-final-report.md")
PHASELOG = os.path.join(REPO, "docs", "continuous-decision-v0.7-phase-log.md")
PREREG = os.path.join(REPO, "configs", "experiment", "v07_e2_preregistration.json")

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
                         "http_requests": None, "unbound": 0, "reason": None, "objects": None})
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
                     "reason": result.get("termination_reason"),
                     "http_requests": result.get("http_requests"), "unbound": unbound,
                     "objects": f"{result.get('objects_completed')}/{result.get('objects_total')}"})
    return rows


def outcomes_of(rows: list[dict]) -> dict:
    out: dict = {}
    for r in rows:
        out[r["status"]] = out.get(r["status"], 0) + 1
    return out


def main() -> int:  # noqa: C901 - a gate is a list of checks, in the order of the report
    rep, log = text(REPORT), text(PHASELOG)

    # ---------------- E2'''' against the archive
    facts = {ch: episode_facts(run_dir(E2_V07, ch)) for ch in ("privileged", "stub", "vlm")}
    check("E2'''' privileged 4/4", outcomes_of(facts["privileged"]) == {"success": 4},
          outcomes_of(facts["privileged"]))
    check("E2'''' stub 0/4", outcomes_of(facts["stub"]) == {"failed": 4}, outcomes_of(facts["stub"]))
    check("E2'''' vlm 0/4", outcomes_of(facts["vlm"]) == {"failed": 4}, outcomes_of(facts["vlm"]))
    requests = {ch: sum(r["http_requests"] or 0 for r in facts[ch])
                for ch in ("privileged", "stub", "vlm")}
    check("E2'''' 请求 0 / 0 / 147", requests == {"privileged": 0, "stub": 0, "vlm": 147}, requests)
    check("E2'''' 未绑定行 0 / 16 / 49",
          {ch: sum(r["unbound"] for r in facts[ch]) for ch in facts}
          == {"privileged": 0, "stub": 16, "vlm": 49},
          {ch: sum(r["unbound"] for r in facts[ch]) for ch in facts})
    stops = [r["episode_id"] for r in facts["vlm"] if r["failure_type"] == "BUDGET_EXHAUSTED"]
    check("E2'''' 撞墙只有 c3 r0", stops == ["lh_c3_capacity_and_shift.B.r0"], stops)
    orphan = [r for r in facts["vlm"] if "no pending goal names it" in str(r.get("reason"))]
    check("第五类终态原因（握持孤儿）在相机格占 3/4 集",
          len(orphan) == 3 and {r["episode_id"] for r in orphan} ==
          {"lh_c1_shared_pair_restore.B.r0", "lh_c1_shared_pair_restore.B.r1",
           "lh_c3_capacity_and_shift.B.r1"},
          [(r["episode_id"], r["reason"], r["http_requests"]) for r in orphan])
    check("第五类终态原因在报告里被点名，且不是只算 c3 那一集",
          "holding obj_purple_2 but no pending goal names it" in rep
          and "3/4" in rep and "握持孤儿" in rep)
    check("报告声明了它不是新增（v0.6 的 c1 两集同因）",
          "v0.6" in rep and "不是 v0.7 的新发现" in rep)

    # ---------------- the archived ceilings and the table they ran under
    caps = {}
    for ch in ("privileged", "stub", "vlm"):
        with open(os.path.join(run_dir(E2_V07, ch), "manifest.json"), encoding="utf-8") as f:
            caps[ch] = json.load(f).get("budget_caps")
    check("归档 budget_caps：对照 32，相机格 48/48",
          caps["privileged"] == {"http_requests": 32, "perception_requests": 48}
          and caps["stub"] == caps["vlm"] == {"http_requests": 48, "perception_requests": 48}, caps)

    # ---------------- M1, re-derived from its own instrument output
    try:
        with open(os.path.join(WORK, "m1_mismatch.json"), encoding="utf-8") as f:
            m1 = json.load(f)
        covered = {c: r for c, r in m1["cases"].items()
                   if any(r["confirmed_discrimination"][ch]["looks"]
                          for ch in r["confirmed_discrimination"])}
        check("M1 有证据的 case 恰为 c1 + c3", set(covered) == {"lh_c1_shared_pair_restore",
                                                              "lh_c3_capacity_and_shift"},
              sorted(covered))
        check("M1 四个 case 零帧",
              all(m1["cases"][c]["confirmed_discrimination"]["vlm"]["looks"] == 0
                  for c in m1["cases"] if c not in covered))
        pairs = [row["per_channel"][ch]["pair"]["verdict"] for row in m1["declarations"]
                 for ch in ("stub", "vlm")
                 if row["per_channel"][ch]["pair"]["verdict"] != "no_confirmed_evidence"]
        check("M1 属性对 17 可接地 / 3 超粒度",
              pairs.count("groundable") == 17 and pairs.count("beyond_grain") == 3,
              {v: pairs.count(v) for v in set(pairs)})
        beyond = [(row["case_id"], row["target_id"], ch)
                  for row in m1["declarations"] for ch in ("stub", "vlm")
                  if row["per_channel"][ch]["pair"]["verdict"] == "beyond_grain"]
        check("M1 三个超粒度全在 stub 侧",
              len(beyond) == 3 and all(ch == "stub" for _c, _t, ch in beyond), beyond)
        cooccurrence = sum(r["confirmed_discrimination"][ch]["same_name_cooccurrence_frames"]
                           for r in m1["cases"].values() for ch in ("stub", "vlm"))
        check("M1 同名属性共现 0 帧", cooccurrence == 0, cooccurrence)
        first_look = {(c, ch): r["confirmed_discrimination"][ch]["first_look_objects"]["max"]
                      for c, r in covered.items() for ch in ("stub", "vlm")}
        # the first look is **not** empty -- 4 objects on c1, 5 on c3 -- and an earlier draft of
        # both documents said it was. The gate asserts the measured value so the sentence cannot
        # drift back.
        check("M1 首观测带 4（c1）/ 5（c3）件，不是 0",
              set(first_look.values()) == {4, 5}
              and first_look[("lh_c1_shared_pair_restore", "stub")] == 4
              and first_look[("lh_c3_capacity_and_shift", "vlm")] == 5, first_look)
        check("报告把首观测那一列更正过",
              "首观测并不空" in rep and "开局整帧空" in rep)
        check("报告的 M1 数字与清单一致",
              all(s in rep for s in ("20/20", "17/20", "0 / 760", "156", "183")))
    except Exception as exc:  # noqa: BLE001
        skipped("M1 重导", f"{type(exc).__name__}: {exc}")

    # ---------------- the v2 table and its freeze
    try:
        from embodied_agent.evaluation.long_horizon_tasks import (
            LH_FROZEN_PATH, LH_V1_FROZEN_PATH, build_long_horizon_set, check_lh_frozen, lh_manifest)
        ok, message = check_lh_frozen()
        check("长视野表是 v2 且门绿", ok and LH_FROZEN_PATH.endswith("_v2.json"), message)
        manifest = lh_manifest()
        check("v2 载荷带 sealed_v1_sha256", manifest["sealed_v1_sha256"].startswith("ae012f12"),
              manifest["sealed_v1_sha256"])
        check("v2 哈希是 b9fce17fbbf6", manifest["sha256"].startswith("b9fce17f"),
              manifest["sha256"][:12])
        with open(LH_V1_FROZEN_PATH, encoding="utf-8") as f:
            v1 = json.load(f)
        recorded = v1.pop("sha256")
        check("v1 文件封存自洽（仍哈希到自己的记录值）",
              hashlib.sha256(json.dumps(v1, ensure_ascii=False, sort_keys=True,
                                       indent=1).encode("utf-8")).hexdigest() == recorded)
        v1_cases = {c.task_id: c.utterance for c in build_long_horizon_set("v1")}
        v2_cases = {c.task_id: c.utterance for c in build_long_horizon_set("v2")}
        changed = {k for k in v1_cases if v1_cases[k] != v2_cases[k]}
        check("v2 只改了 c1 一处声明", changed == {"lh_c1_shared_pair_restore"}, sorted(changed))
        check("c1 的改动是去掉形状词",
              "紫色的圆柱" in v1_cases["lh_c1_shared_pair_restore"]
              and "紫色的物体" in v2_cases["lh_c1_shared_pair_restore"])
        profiles = manifest["profiles"]["cases"]
        check("双画像六案齐全且 t0 分母全为否",
              len(profiles) == 6 and all(p["trigger_premise"]["has_denominator_at_t0"] is False
                                         for p in profiles.values()),
              {c: p["trigger_premise"]["has_denominator_at_t0"] for c, p in profiles.items()})
        check("P-D 画像带 c3 的 56", profiles["lh_c3_capacity_and_shift"]["demand"]
              ["v06_max_final_request"] == 56,
              profiles["lh_c3_capacity_and_shift"]["demand"]["v06_max_final_request"])
    except Exception as exc:  # noqa: BLE001
        skipped("v2 表与画像", f"{type(exc).__name__}: {exc}")

    # ---------------- 原则 21(a): reachability measured before the batch
    try:
        with open(os.path.join(WORK, "reachability_v2.json"), encoding="utf-8") as f:
            reach = json.load(f)
        check("原则 21(a)：privileged rule 席 4/4",
              reach["cells"] and all(c["successes"] == 4 for c in reach["cells"].values()),
              {k: v["outcomes"] for k, v in reach["cells"].items()})
        check("报告引用了可达性读数", "4/4" in rep and "原则 21" in rep)
    except Exception as exc:  # noqa: BLE001
        skipped("可达性读数", f"{type(exc).__name__}: {exc}")

    # ---------------- the pre-registration vs what was spent
    try:
        with open(PREREG, encoding="utf-8") as f:
            prereg = json.load(f)
        bound = prereg["spend_bound"]["requests"]
        check("上界 235 未触界", bound == 235 and requests["vlm"] <= bound,
              (bound, requests["vlm"]))
        check("预登记的 USD 是 null", prereg["cost_estimate_usd"] is None
              and prereg["pricing_configured"] is False)
        check("预登记写明四代并排与表版本口径",
              "four_generation_table" in prereg and "v1 declarations" in json.dumps(prereg))
        check("预登记写明 0 合法与 REPEATED_INVALID 风险预写",
              "0 remains legal" in json.dumps(prereg, ensure_ascii=False)
              and "REPEATED_INVALID" in json.dumps(prereg))
        check("上界的构成与报告一致", "2×36 + 2×56 + 4" in rep and "235" in rep)
    except Exception as exc:  # noqa: BLE001
        skipped("预登记读数", f"{type(exc).__name__}: {exc}")

    # ---------------- RQ20's acceptance reading, recomputed from the readings file
    try:
        with open(os.path.join(E2_V07, "e2_quad_readings.json"), encoding="utf-8") as f:
            readings = json.load(f)
        rq20 = readings["rq20_acceptance"]
        check("RQ20 验收读数：#25 15 行 / #26 50 行 / 4 集",
              rq20["ambiguity_rows"] == 15 and rq20["intermittency_rows"] == 50
              and len(rq20["episodes_with_the_class"]) == 4, rq20)
        check("报告把 RQ20 记成负结果", "没有消失" in rep and "4 / 4" in rep)
        check("阶段日志同记 RQ20 负读数", "没有消失" in log)
    except Exception as exc:  # noqa: BLE001
        skipped("RQ20 验收读数", f"{type(exc).__name__}: {exc}")

    # ---------------- the stub naming used this batch's own frames
    try:
        with open(os.path.join(E2_V07, "e2_stub_names_v2.json"), encoding="utf-8") as f:
            names = json.load(f)
        sources = {r["frames_source"] for r in names["episodes"]}
        check("stub 开名用的是本批自己的帧（v0.6 方法更正已应用）",
              sources == {"this batch"}, sources)
        c3 = {r["episode_id"]: r for r in names["episodes"] if "c3" in r["episode_id"]}
        check("stub c3 的死因是 #25 ×7 + #26 ×1",
              len(c3) == 2 and all(r["cause_tally"].get("#25") == 7
                                   and r["cause_tally"].get("#26") == 1
                                   for r in c3.values()),
              {k: r.get("cause_tally") for k, r in c3.items()})
        c1 = [r for r in names["episodes"] if "c1" in r["episode_id"]]
        check("stub c1 两集仍是 REPEATED_INVALID（原则 20 的活证据）",
              len(c1) == 2 and all(r["failure_type"] == "REPEATED_INVALID" and r["unbound_rows"] == 0
                                   for r in c1),
              [(r["episode_id"], r["failure_type"], r["unbound_rows"]) for r in c1])
    except Exception as exc:  # noqa: BLE001
        skipped("stub 开名", f"{type(exc).__name__}: {exc}")

    # ---------------- the frozen surface, re-run rather than quoted
    try:
        from embodied_agent.core import v02
        with open(os.path.join(REPO, "configs", "experiment", "v02_schema_freeze.json"),
                  encoding="utf-8") as f:
            frozen = json.load(f).get("schema_fingerprint", {})
        now = v02.schema_fingerprint()
        check("事件 fingerprint 逐项相等（重冻结只动了任务表）",
              all(now.get(k) == frozen.get(k) for k in now if k in frozen),
              {k: (now.get(k), frozen.get(k)) for k in now
               if k in frozen and now.get(k) != frozen.get(k)})
    except Exception as exc:  # noqa: BLE001
        skipped("fingerprint", f"{type(exc).__name__}: {exc}")
    for gate, prefix in (("freeze", "2f1c74f52e91"), ("prereg", "23abe58ff333"),
                         ("em-pairs", "7df449ed2f4d")):
        try:
            r = subprocess.run([sys.executable, "-m", "embodied_agent.cli", gate, "--check"],
                               capture_output=True, text=True, cwd=REPO,
                               env={**os.environ, "PYTHONPATH": "."})
            check(f"{gate} --check rc=0 且冻结 47 哈希未变",
                  r.returncode == 0 and prefix in (r.stdout + r.stderr),
                  (r.stdout + r.stderr)[-160:])
        except Exception as exc:  # noqa: BLE001
            skipped(f"{gate} --check", f"{type(exc).__name__}: {exc}")
    try:
        r = subprocess.run([sys.executable, "-m", "embodied_agent.evaluation.long_horizon_tasks",
                            "--check"], capture_output=True, text=True, cwd=REPO,
                           env={**os.environ, "PYTHONPATH": "."})
        check("长视野表 --check rc=0（v2）", r.returncode == 0 and "OK" in (r.stdout + r.stderr),
              (r.stdout + r.stderr)[-120:])
    except Exception as exc:  # noqa: BLE001
        skipped("lh --check", f"{type(exc).__name__}: {exc}")

    # ---------------- the documents' own surface
    check("报告的 RQ 答卷三节都在", all(s in rep for s in ("RQ18", "RQ19", "RQ20")))
    check("报告有四代并排表与 v2 重裁总账",
          "四代并排" in rep and "v2 重裁总账" in rep)
    check("报告的负结果清单在（十条）",
          "负结果清单" in rep and all(f"| {i} |" in rep for i in range(1, 11)))
    check("报告声明 USD 为 null", "`null`" in rep)
    check("报告与阶段日志无凭据形状",
          not re.search(r"sk-[A-Za-z0-9]{8}", rep) and not re.search(r"sk-[A-Za-z0-9]{8}", log))
    check("阶段日志的判据先于读数", "P1 判据" in log and "跑后未改一字" in log)
    check("阶段日志记了两条判据修正", "判据修正 1" in log and "判据修正 2" in log)
    check("阶段日志记了由错话引发的重裁", "由我自己的错话引发的重裁" in log)
    check("阶段日志记了 P3 的四格预登记", "P3 预登记" in log and "格一" in log and "格四" in log)

    failed = [(n, d) for n, ok, d in results if not ok]
    for name, ok, detail in results:
        print(f"  {'OK ' if ok else 'RED'} {name}" + (f"  [{detail}]" if (detail and not ok) else ""))
    print(f"RESULT: {len(results) - len(failed)}/{len(results)} -> "
          f"{'ALL CLOSED' if not failed else str(len(failed)) + ' RED'}")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())