# S1 验收证据包(A1~A6)

生成时间:2026-09-18 04:08
代码状态:embodied_agent 包(core/adapters/evaluation),旧二维原型保留为测试替身。

## A1 — 规则基线 + 物理执行,S1-clean ≥ 80%
**达标:81/90 = 90.0%,Wilson 95% CI [0.821, 0.946](下界 > 0.80)**
- 3 物体:30/30(100%),4 物体:27/30(90%),5 物体:24/30(80%)
- 证据:runs/s1_clean_rule_recoveryon_20260918_034252/report.json、results.csv,每 episode 的 config.json / events.jsonl / summary.json / final_frame.png

## A2 — 在线 DeepSeek 端到端 ≥ 80%
**达标:80/90 = 88.9%,Wilson 95% CI [0.807, 0.939](下界 > 0.80)**(2026-09-18 更新,真实 API key 在线运行)
- 分层:3 物体 29/30(96.7%),4 物体 27/30(90.0%),5 物体 24/30(80.0%)
- M4 前置门:dev 20 条指令在线目标解析 20/20、计划有效 20/20
- 在线调用记账(model_calls.jsonl):105 请求、98,206 tokens、平均延迟 1.54s、重规划请求 15 次
- 无恢复对照 E0:80/90(88.9%)—— 恢复开关在 clean 集上不降低成功率
- 语言解析错误计入端到端成绩;无静默规则回退(适配器构造失败即报错)
- 证据:runs/s1_clean_deepseek_recoveryon_20260918_051112/report.json 等

## A3 — S1-fault 恢复配对增益 ≥ 20pp 且 95% 区间下界 > 0
**达标:recovery 组 19/30(63.3%) vs no-recovery 组 0/30(0%),平均增益 +63.3pp**
- 按配置聚类 bootstrap 95% CI:[0.467, 0.8](下界 0.467 > 0.20)
- 配对:19 胜 / 0 负 / 11 平;精确符号检验 p = 2^-19 ≈ 1.9e-6
- 故障:第一次抓取下降目标冻结偏移(60–85mm,方向限定可达侧);no-recovery 组全部终止于 GRASP_MISS(0/30),证实故障注入真实有效
- recovery 组剩余失败分布:GRASP_MISS 3(重试耗尽)、IK/路径 3、TARGET_FULL 6、INVALID_PLAN 2(held unknown)、异常 2 —— 均有界终止,无假成功
- 证据:runs/s1_fault_rule_recoveryon_20260918_035234/report.json vs runs/s1_fault_rule_recoveryoff_20260918_035602/report.json;命令 a3 输出见 acceptance_summary.json

## A4 — negative 用例
**达标:10/10 在预算内终止/澄清**
- 覆盖:歧义指代("把那个东西收好")、不存在颜色/实体 ID、未知目标、空目标、属性冲突、堆叠越界请求;
  非法动作从未执行(事件日志中无对应 skill_call)
- 另:合法边界(重复绑定、三物归一盘)正确执行成功
- 证据:runs/negative_rule_recoveryon_20260918_034237/report.json

## A5 — 演示与回放
**完成:runs/demo_20260918_040722**
- 5 物体多物体 episode(independent score 5/5):episode_5obj/{config,events,summary,final}.json/png
- 物理恢复回放:recovery_demo/ 8 张逐技能帧(pick 抓空 → safe_retreat → 重抓取 → place)+ events.jsonl 中
  fault_injection / GRASP_MISS / recovery / step_verify 事件链
- 轨迹回放:replay 命令重放已记录计划,complete_success=true
- 模型响应重放:model-replay 命令(本 demo 为 rule 规划,无模型响应事件;LLM episode 可用)

## A6 — 安装/复现
**完成**
- README.md:安装、smoke、指定 episode 复现、CLI 全集
- requirements.txt:pybullet 3.2.7 / numpy 2.4.6 / pydantic 2.13.5 / pillow 12.3.0 / pytest 9.1.1(Python 3.11)
- 每 run 目录 config.json 为完整配置快照;固定种子列表在 evaluation/tasks.py 中版本化
- 环境预检:outputs/w0_precheck/precheck.json(全部 PASS)

## 总体
S1 六项验收:A1 ✓ A3 ✓ A4 ✓ A5 ✓ A6 ✓;A2 阻塞于 API key(基础设施就绪)。

---

# S1 完成定义核对(实施规格 §2,十条逐项)

1. PyBullet 固定 Panda 单臂 — **满足**(franka_panda/panda.urdf,基座 0.30m,W0 预检记录)
2. 真实夹爪接触,无瞬移/吸附 — **满足**(物理接触+摩擦;reset 仅影子状态;故障注入只改下降目标)
3. 3~5 物体逐个归位 — **满足**(3/4/5 物体分层评测)
4. 同一 Runtime 切换 rule/deepseek — **满足**(planner 参数注入,技能与仿真零改动)
5. DeepSeek 结构化 Goal/Plan + 客户端校验 — **满足**(JSON mode + Pydantic + PlanValidator;dev 20/20)
6. 每次 pick/place 强制重观察验证 — **满足**(Runtime._execute_plan 强制,LLM 无法关闭)
7. 一次抓空可检测可恢复;其他异常分类有界退出 — **满足**(GRASP_MISS 恢复链;10 类失败码)
8. 独立 Evaluator 真值判分,Agent 不可读 — **满足**(依赖注入隔离 + 反向测试 tests/unit/test_information_isolation.py)
9. 固定任务集、无恢复对照、统计、事件日志、视频、复现说明 — **满足**(5 个 suite;events.jsonl envelope;video.mp4;README)
10. 规则基线与在线 DeepSeek 均 ≥80%,恢复有稳定正向增益 — **满足**(90%/88.9%;+63.3pp,CI [0.467, 0.8])

## 结论
S1 完成定义十条全部满足。新增差距修复:API key 配置(.env,gitignore)、CLI 契约(6 命令+退出码)、
事件 envelope v1、model_calls.jsonl、frames/video.mp4、负例扩至 12、测试四层拆分、运行矩阵
B0/B1/E0/E1 全部完成。
