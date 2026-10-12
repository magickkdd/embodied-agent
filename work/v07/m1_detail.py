"""The M1 rows that decide the v2 re-adjudication, printed the way D4'''' needs them.

`m1_mismatch.py` writes the whole judgement; this is the reading surface: per declaration and
per channel, the pair-level verdict (what a declaration actually binds by), the confirmed colour
and shape vocabularies, and the degeneracy warning. Only the cases with confirmed camera evidence
are printed -- the rest say so in one line rather than dressing an absence up as a verdict.
"""
from __future__ import annotations

import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "m1_mismatch.json"), encoding="utf-8") as f:
    M1 = json.load(f)


def main() -> int:
    covered = [case_id for case_id, reading in M1["cases"].items()
               if any(reading["confirmed_discrimination"][ch]["looks"]
                      for ch in reading["confirmed_discrimination"])]
    uncovered = [case_id for case_id in M1["cases"] if case_id not in covered]
    print(f"有已证实相机证据的 case（{len(covered)}）：{', '.join(sorted(covered))}")
    print(f"无已证实相机证据的 case（{len(uncovered)}）：{', '.join(sorted(uncovered))}")

    print("\n=== 逐声明的 pair 级判定（有证据的 case）")
    for case_id in sorted(covered):
        print(f"-- {case_id}")
        for row in M1["declarations"]:
            if row["case_id"] != case_id:
                continue
            for channel in ("stub", "vlm"):
                cell = row["per_channel"][channel]
                print(f"   {row['target_id']:<14}{row['declared']['color']}/{row['declared']['shape']:<9}"
                      f"{channel:<5} pair={cell['pair']['verdict']:<26}"
                      f"pair_frames={cell['pair']['pair_frames']:<4} "
                      f"lone={cell['pair']['pair_frames_without_namesake']:<4}"
                      f"color={cell['color']['verdict']:<26}"
                      f"shape={cell['shape']['verdict']}")

    print("\n=== 超粒度 / 条件可接地的属性，逐条带证据链")
    for row in M1["declarations"]:
        if row["case_id"] not in covered:
            continue
        for channel in ("stub", "vlm"):
            cell = row["per_channel"][channel]
            for key in ("color", "shape", "pair"):
                verdict = cell[key]["verdict"]
                if verdict in ("groundable", "no_confirmed_evidence"):
                    continue
                print(f"   {row['case_id'][:12]:<12}{row['target_id']:<14}{channel:<5}{key:<6}"
                      f"{verdict:<28}{cell[key]['evidence']}"
                      f"{' condition: ' + cell[key]['condition'] if cell[key].get('condition') else ''}")

    print("\n=== 已证实词表（逐代合并，逐通道）")
    for case_id in sorted(covered):
        for channel in ("stub", "vlm"):
            c = M1["cases"][case_id]["confirmed_discrimination"][channel]
            print(f"   {case_id:<30}{channel:<5}looks={c['looks']:<5}"
                  f"colours={','.join(c['confirmed_colours'])}  "
                  f"shapes={','.join(c['confirmed_shapes'])}  "
                  f"objs/frame={c['objects_per_frame']}  "
                  f"cooccurrence={c['same_name_cooccurrence_frames']}")

    print("\n=== 每集 look 数（需求画像的原料，P3 用）")
    per_case = collections.defaultdict(list)
    for row in M1["declarations"]:
        per_case[row["case_id"]].append(row)
    for case_id in sorted(covered):
        reading = M1["cases"][case_id]["confirmed_discrimination"]
        targets = len(M1["cases"][case_id]["targets"])
        for channel in ("stub", "vlm"):
            looks = reading[channel]["looks"]
            print(f"   {case_id:<30}{channel:<5}looks_total={looks:<5}"
                  f"targets={targets:<3}looks_per_target={looks / max(targets, 1):.2f}  "
                  f"first_look_objects={reading[channel]['first_look_objects']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())