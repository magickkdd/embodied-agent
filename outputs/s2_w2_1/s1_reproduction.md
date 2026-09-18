# W2.1:S1 复现与错误归因报告

日期:2026-09-18|依据:Next-Stage-Embodied-Agent-Spec-v1.0 §9 W2.1
性质:只读分析,未修改 planner/skill/物理参数(规格 §14.5)

## 1. 状态确认(W2.1-1)

- 代码入口:`python -m embodied_agent.cli {doctor,sim-smoke,run,evaluate,report,replay,llm}`
- 配置:`configs/models/deepseek.yaml`(provider/key_env/prompt_version=s1-plan-v1)、`.env`(gitignore)
- 测试:tests/{unit,contract,integration,online},离线 24 passed
- 任务集生成:`embodied_agent/evaluation/tasks.py`(smoke/dev/s1_clean/s1_fault/negative,固定 seed)

## 2. 产物定位(W2.1-2)

正式批次(与 evidence.md 引用一致,均为完整 90/30 集产物):

| 批次 | 目录 | episodes |
|---|---|---|
| B1 rule clean | runs/s1_clean_rule_recoveryon_20260918_034252 | 90 |
| E1 deepseek clean | runs/s1_clean_deepseek_recoveryon_20260918_051112 | 90 |
| E0 deepseek clean 无恢复 | runs/s1_clean_deepseek_recoveryoff_20260918_043353 | 90 |
| B1 rule fault×3 | runs/s1_fault_rule_recoveryon_20260918_052515 | 90 |
| B0 rule fault×3 | runs/s1_fault_rule_recoveryoff_20260918_044811 | 90 |
| EF1 deepseek fault | runs/s1_fault_deepseek_recoveryon_20260918_053722 | 30 |
| EF0 deepseek fault | runs/s1_fault_deepseek_recoveryoff_20260918_045231 | 30 |

注:runs/ 中存在更早批次(如 03:14 的 rule clean 40/90),为物理 bug 修复前产物,不属正式批次,已在报告中区分。

## 3. 独立重算核对(W2.1-3,work/w2_1_recompute.py)

重算脚本不复用 runner 的汇总逻辑,直接从每集 summary.json 计算:

| 指标 | 重算 | 官方报告 | 一致 |
|---|---|---|---|
| B1 clean 总成功率 | 81/90 = 0.900 [0.821, 0.946] | 0.900 [0.821, 0.946] | ✓ |
| B1 分层 3/4/5 | 1.000 / 0.900 / **0.800** | 同 | ✓ |
| E1 clean | 80/90 = 0.889 [0.807, 0.939] | 0.889 [0.807, 0.939] | ✓ |
| E1 分层 3/4/5 | 0.967 / 0.900 / **0.800** | 同 | ✓ |
| B1 fault | 57/90(按配置 19/30) | 同 | ✓ |
| B0 fault | 0/90(全部 GRASP_MISS) | 同 | ✓ |
| fault 配对 | 30 配置,19 胜 0 负 11 平 | 同 | ✓ |
| 每对象成功率 B1/E1 | 0.969 / 0.961 | (新增指标) | — |

结论:Project_summary 与 evidence.md 中的数字全部可由原始产物复现。

## 4. 5 物体失败归因(W2.1-4,work/w2_1_attribute.py)

全部 12 个 5 物体失败 episode(B1 6 个 + E1 6 个)逐集读取 events.jsonl,按 §9.1 分类:

| 类别 | B1_rule | E1_deepseek | 典型证据 |
|---|---|---|---|
| capacity | **3** | 0 | TARGET_NO_FREE_SLOT,失败时目标盘已 3 物,槽位模式只有 4 槽且占用半径 0.085m 排除法失效 |
| place_geometry | 2 | 3 | IK_OR_PATH_UNREACHABLE,均发生在已放 3+ 物后:转移栅栏点或下降路径被占用托盘挤出可达域 |
| interference | 1 | 0 | ANOMALOUS_CONTACT,placed=5 后续步骤碰撞已放物体 |
| grasp | 0 | 0 | (5 物体层无;GRASP_MISS 失败集中在 fault 集) |
| planner | 0 | **3** | 重规划输出以 place 开头(place-before-pick 被校验器正确拒绝)→ 见 §4.1 |
| verification | 0 | 0 | — |

明细 CSV:outputs/s2_w2_1/error_attribution.csv

### 4.1 E1 的 INVALID_PLAN 深查(3 例)

三个案例模式完全一致:4/5 完成后触发重规划,此时机械臂**实际持有第 5 个物体**;DeepSeek 重规划计划以 `place obj_X` 开头但该对象未出现在 pick 步骤中,PlanValidator 正确拒绝("place before pick / gripper starts idle"),1 次修复后仍同类,预算耗尽终止。

判定:不是模型幻觉实体,而是 **replan 上下文缺陷**——持有状态(held_object)虽在状态摘要里,但没有作为"首步必须是 place(所持对象)"的硬约束传入,校验器也没有把该反馈回传给修复请求。系统行为正确(拒绝非法计划、有界退出),但白白损失了 3 个本可完成的 episode。

### 4.2 与 S1 分层递减(96.7→90→80%)的关系

- 5 物体层 12 个失败里 **6 个与共享目标区域直接相关**(3 capacity + 3 place_geometry 均发生在多物同盘场景);
- E1 另有 3 个 replan 上下文失败与物体数无直接关系,但 5 物体任务重规划概率更高(更多放置→更多验证失败→更多重规划),间接触发;
- 结论:**"5 物体失败集中于共享目标区域的容量与干扰"这一 Project_summary 假设成立,且新增一个同等量级的 replan 上下文缺陷**。

## 5. S2 优先级建议(W2.1-5)

按可挽回的失败数排序(5 物体层 12 失败 + fault 集 33 失败的分布):

1. **W2.2 槽位/容量规划(PlacementPlanner)**——直接对应 6/12(3 capacity + 2 B1 place_geometry 部分);现 4 槽固定模式 + 0.085m 排除法在 3 物同盘时耗尽。需要:容量显式建模、footprint 感知的槽位生成、已放物体作为障碍输入(规格 §4.2)。
2. **replan 上下文修复(归入 W2.4)**——对应 E1 的 3/12:持有状态作为硬约束进入 prompt 与校验反馈;预期同时降低 5 物体层的重规划失败率。
3. **W2.3 稳健 place**——place_geometry 的转移栅栏点可达性问题:占用托盘把栅栏高度/路径挤出可达域,需要路径与槽位联合考虑(可先在 PlacementPlanner 槽位评分中加"可达性"项)。
4. fault 集剩余失败(GRASP_MISS 重试耗尽 9、IK 9 等)在上述三项完成后重测,预计随放置质量改善而下降。

建议下一步按规格 §9 顺序进入 W2.2,同时把 replan 上下文修复并入 W2.4 的验收测试。

## 6. 产物索引

- 重算指标:outputs/s2_w2_1/recomputed_metrics.json
- 错误归因:outputs/s2_w2_1/error_attribution.csv
- 失败 episode 回放入口(抽查用):
  - B1 capacity:`python -m embodied_agent.cli replay --episode runs/s1_clean_rule_recoveryon_20260918_034252/s1_clean_5obj_s502_20260918_034834_160`
  - E1 planner:`python -m embodied_agent.cli llm --episode runs/s1_clean_deepseek_recoveryon_20260918_051112/s1_clean_5obj_s502_20260918_051929_613`
  - 其余见 CSV episode 列(每个目录含 events.jsonl / frames/ / video.mp4)
