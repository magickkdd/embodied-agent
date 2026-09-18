# S1 运行矩阵报告(规格 §13.2 B0/B1/E0/E1)

生成时间:2026-09-18 05:47

## s1-clean(每模式 90 episodes)

| 模式 | Planner | Recovery | 成功/总数 | 成功率 | Wilson 95% CI |
|---|---|---|---|---|---|
| B1 | rule | on | 81/90 | 90.0% | [0.821, 0.946] |
| E1 | deepseek | on | 80/90 | 88.9% | [0.807, 0.939] |
| E0 | deepseek | off | 80/90 | 88.9% | — |

- A1(B1 ≥ 80%)✓;A2(E1 ≥ 80%)✓,Wilson 下界 0.807 > 0.80
- 分层:3 物体 96.7%、4 物体 90.0%、5 物体 80.0%
- 在线调用:model_calls.jsonl 共 105 请求、98,206 tokens、平均延迟 1.54s、重规划 15 次

## s1-fault(30 个冻结故障配置;rule 模式每配置 3 次确定性重复,deepseek 模式每配置 1 次)

| 模式 | Planner | Recovery | 配置胜/负/平 | 成功率 |
|---|---|---|---|---|
| B1 | rule | on | — | 57/90(按配置 19/30) |
| B0 | rule | off | — | 0/90 |
| EF1 | deepseek | on | — | 19/30 |
| EF0 | deepseek | off | — | 0/30 |

- A3:B1−B0 = +63.3pp,聚类 bootstrap 95% CI [0.467, 0.8](下界 > 20pp 要求)✓
- EF1−EF0 = +63.3pp(19 胜 0 负 11 平),与 rule 模式一致 —— 恢复增益跨 planner 成立
- no-recovery 组 0/90 与 0/30:证实故障注入真实有效,不存在隐藏吸附兜底

## negative(12)与 smoke(5)
- negative 12/12 预算内澄清/终止 ✓(含目标无空间 TARGET_FULL、预算耗尽两个新增边界)
- smoke:3/3+5/5 物体任务全部成功,抓空故障恢复成功,非法目标正确拒绝

## 证据目录
- B1(clean):runs/s1_clean_rule_recoveryon_20260918_034252
- E1:runs/s1_clean_deepseek_recoveryon_20260918_051112;E0:runs/s1_clean_deepseek_recoveryoff_20260918_043353
- B1(fault):runs/s1_fault_rule_recoveryon_20260918_052515;B0:runs/s1_fault_rule_recoveryoff_20260918_044811;EF1:runs/s1_fault_deepseek_recoveryon_20260918_053722;EF0:runs/s1_fault_deepseek_recoveryoff_20260918_045231
- negative:runs/negative_rule_recoveryon_20260918_042508;demo:runs/demo_20260918_040722
- API key 泄漏检查:runs/、outputs/、configs/、embodied_agent/ 均无 key ✓(key 仅在 .env,已 gitignore)
