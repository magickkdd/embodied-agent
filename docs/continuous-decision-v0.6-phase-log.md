# Continuous-Decision Embodied Agent v0.6 —— 阶段日志

执行纪律沿 v0.3/v0.4/v0.5：**先预登记、先测量、后说话；判据进测试与仪器；每条读数带论域；
负结果保留并给原因；`cost_estimate_usd` 无单价时保持 `None`。** SPEC 是
`Continuous-Decision-Embodied-Agent-SPEC-v0.6.md`；读数（P4 之后）将记在 v0.6 最终报告。

v0.6 的两条新纪律（SPEC §4 原则 18–19）：**修环不修症状**——#26 的修复候选必须先有 B1 的
天花板与误绑风险读数，#25 的候选必须先有 B2 的分支刻画，"邻帧融合能救"与"逐帧唯一性能绑对"
都是待测假设而不是直觉的通行证；**预算是账本不是墙**——每集请求上限的语义由 Q1 裁定给出，
上界永远按构成外推，墙的位置随裁定可以动，账的口径动不得。

---

## P0 预检（零成本，2026-10-11）

### 边界验证（当场重跑，未转引）

解释器：`/home/czx/miniforge3/envs/embodied/bin/python`（conda 环境 `embodied`）。

| 门 | 输出 | rc |
| --- | --- | --- |
| `python -m embodied_agent.cli freeze --check` | `frozen list matches: 2f1c74f52e91` | 0 |
| `python -m embodied_agent.cli prereg --check` | `pre-registration matches the code: 23abe58ff33372ffa6f62a608221dfc1af2006f85ae50f7651a0f28451aae7b3` | 0 |
| `python -m embodied_agent.cli em-pairs --check` | `em set matches: 7df449ed2f4d` | 0 |

三条哈希与 v0.5 报告 §0 逐位一致。`tests/contract/test_v02_contracts.py` **25 passed**
（`schema_fingerprint()` 与 `v02_schema_freeze.json` 逐项相等）⇒ v0.6 的四个落点
（`core/contracts.py` 的 `Budgets`、`core/runtime.py` 的 `BudgetLedger`、
`perception/arm.py` 与 `benchmark/runtime_alfred.py` 的判死执行点、`evaluation/preregistration.py`
的预登记口径）**都不在 `core/v02.py` 的哈希面上**，SPEC §2.2 的冻结面约束成立。

### SPEC 点名的代码锚点（2026-10-11 工作树实测；判据锚定行为，不锚定行号）

| SPEC §14 的行号 | 实测位置 | 内容 |
| --- | --- | --- |
| `contracts.py:434` | `embodied_agent/core/contracts.py:434` | `max_http_requests: int = 32`（逐集 HTTP 上限，默认值） |
| `core/runtime.py:75` | `embodied_agent/core/runtime.py:75` | `class BudgetLedger`，`http_requests` 是**单计数器**（`__init__` 第 84 行自增） |
| `perception/arm.py:472` | `embodied_agent/perception/arm.py:472` | `PerceptRuntime._preflight_trip`：`ledger.http_requests >= max_http_requests` ⇒ `BUDGET_EXHAUSTED` |
| `benchmark/runtime_alfred.py:244` | `embodied_agent/benchmark/runtime_alfred.py:244` | ALFRED 侧同形判死 |
| `evaluation/preregistration.py:114` | `embodied_agent/evaluation/preregistration.py:114` | `per_episode_http_cap` = 各 formal case 的 `max_http_requests` 最大值（预登记的**输入面**，不是冻结面，SPEC §2.2 原文） |

五处行号全部与 SPEC 快照一致。**`EpisodeResult.http_requests` 是逐集冻结面**（SPEC §2.2 默认不动），
Q1 的分账因此只能在 `BudgetLedger` 与事件流导出层做——这是本阶段第一处边界。

### 残留与裁定的入口账（v0.5 §8 + §13）

| 账 | v0.5 的落点 | v0.6 的入口动作 |
| --- | --- | --- |
| #27 每集 32 次预算撞墙（E2'' 的 39/32） | 负结果 #4 | **Q1 裁定**（P1，D2'''） |
| #26 间歇漏检 38 个项-轮 | 负结果 #3（"修 b 会自动修 a"被证伪） | **B1 零花费天花板**（P2），修复形状在 D3''' |
| #25 c3 两黄歧义绑定（E2'' 仍 8/12） | 负结果 #7（歧义分支 0 次走到） | **B2 分支刻画**（P2），三候选在 D4''' |
| H2（初始视图无边） | v0.5 报告 §4 H2，187 初始视图 0 反例 | **契约测试**（P1） |
| H1 干预式验证批（≈930 请求） | v0.5 报告 §4 H1 | P4，排在 Q1 裁定之后（排序裁定） |

**排序裁定（用户，2026-10-11，SPEC §13 已落账）**：#27 裁定 → #26 零花费定量 → #25 设计裁定
→ 按读数修复 → E2'''；**H1 排在 #27 裁定之后**（它的上界式子依赖预算语义的答案）。
本日志的工序顺序照此。

### v0.5 封存与身份纪律

`docs/continuous-decision-v0.5-final-report.md` 与 `work/v05/*` 一律只读；v0.6 的仪器落
`work/v06/`（B1 可复用 v0.5 的重放基座，但**以副本形式**进 `work/v06/`，不回写原件）。
`/home/czx/embodied-agent-batches/{v04,v05}/**` 只读；新产物落 `.../v06/`。

**提交**：`Continuous-Decision-Embodied-Agent-SPEC-v0.6.md` + 本日志开篇。

---

## P1 Q1 预算语义裁定与分账（零成本，2026-10-11）

### 裁定的输入：`work/v06/q1_split.py`（归档零花费重导）

| 语料 | 做出 | 归属 | 感知 | 决策 | 单集 |
| --- | --- | --- | --- | --- | --- |
| v0.4 E2' vlm 格（4 集） | 132 | 132 | **132** | **0** | 18–39 |
| v0.5 E2'' vlm 格（4 集） | 148 | 114 | **148** | **0** | 34–39（另 34 次归属不到的请求在死于 429 的那集上） |
| v0.4 E1' 模型席（34 集，3 个 run） | 641 | — | **0** | **641** | 5–40 |

**一个数管着两种花**：相机格的 280 次请求**全部是看图**（rule 策略不发请求），
模型席的 641 次**全部是决策**。重试 10–14 次/集、schema 修 2–6 次/集，说明"看一次"的
实际成本是 1.3–1.5 次请求——这就是 39/32 的来历。另记：上限是**轮前预检**
（`perception/arm.py:_preflight_trip`），所以单集实测可以到 40（32 加上最后一轮已花的部分）。

**D2''' 裁定（用户，2026-10-11）**：**A+B**——分账 **且** 按构成重定价 **且** 感知子上限 **48**
（实测峰值 39 + 余量）。理由：只做 A，E2''' 相机格按构造再撞 32；只做 B，分账不判死。

### 改动形状

| 位置 | 改动 |
| --- | --- |
| `core/runtime.py` | `DEFAULT_PERCEPTION_REQUEST_CAP = 48`；`BudgetLedger` 增 `perception_requests` / `decision_requests` 两本账 + `charge_perception_requests` / `charge_decision_requests`；`http_remaining()` 同时报两本账与**未归属余额**（共享目标解析走 `charge_requests`，它谁也不属于） |
| `core/runtime.py` | 新增 `_charge_round` 接缝：默认就是 v0.5 的 `charge_requests(...)`，**特权通道逐字不变** |
| `perception/arm.py` | 覆写 `_charge_round`（决策一本、感知一本）；`_finalize` 的尾账改记感知；`_preflight_trip` 两道门，总数与感知各一条，**各自在 note 里自报是哪一本** |
| `evaluation/run.py` | `apply_http_caps()`：总上界走 case 预算的**副本**，感知子上限作为运行期参数返回；`run_group`/`run_one_episode` 与四个装配点透传 |
| `cli.py` | `--http-cap` / `--perception-cap`（进 `_perception_kwargs`，落 manifest 的 `budget_profile`） |
| 三个装配器（`perception/arm.py`、`episodic/arm.py`、`acquisition/arm.py`） | 各加一个 `perception_cap` 关键字并透传 |

### 撞上冻结面的一次，当场改设计（记在这里，不藏）

第一版把子上限做成 **`Budgets` 的新字段**（`max_perception_requests: int = 48`）。
`cli freeze --check` 立刻红：

```
MISMATCH: task list drifted: frozen 2f1c74f52e91 != live d3d511e20d0f
```

原因：`frozen_manifest()` 把每个 case 的 `budgets` 一并哈希，**冻结任务表带走了预算面**。
改法不是重冻结（SPEC §2.2/§10 的非目标），而是**把子上限从冻结记录里搬出去**：它是批的
属性，就做成运行期参数，默认值由测量给出。契约测试里留了一条把这个决定钉死：
`assert not hasattr(Budgets(), "max_perception_requests")`——
**谁想把它挪回冻结面，这条会红**。

### 三条既有契约测试的当场修订（理由逐条落账）

| 测试 | 红因 | 修订 |
| --- | --- | --- |
| `test_v02_perception_arm.py::test_the_arm_overrides_ten_seams_and_nothing_else` | `PerceptRuntime` 多了一个 `_charge_round` 接缝 | 改为 **eleven**，并在 docstring 里写明第十一个接缝是什么、为什么；断言的**用途**（"没有第十二个未经审阅的覆写"）不变 |
| `…::test_a_look_is_charged_against_the_http_ceiling` | 该测试钉住 `_requests_used` 会清零 `_looks_unbilled`；分账后清零跟着**记账**走 | 改为断言两半：`_requests_used` 只给总数（不再清零），`_charge_round` 记账并清零，且两本账之和 = 总数 |
| `…::test_the_http_ceiling_ends_the_episode_that_spends_it` | 假 ledger 只有 `http_requests`，新门要读 `perception_requests` | 假 ledger 补齐两本账与子上限，并**新增断言**：感知账单独撞满时也能结束一集，且 note 自报是哪一本 |

### H2 契约测试（`tests/contract/test_v06_plan_edges.py`，3 条）

写它的时候问出一个 v0.5 读数没有问的问题：**这些依赖边是谁写的？**
答案是 **`planning/subgoals.py` 推导出来的，不是模型写的**——
`_capacity_dependencies` 问放置仪器"这个托盘还剩几个可行槽"，位移规则问"有没有谁正坐在
别人要去的地方"，两者产出的 note 就是归档里那三句一模一样的话（`"… was displaced out of
… to let … in and must be restored before the task ends"`）。模型的 plan 载荷只产出 *steps*。

于是 H2 从一句经验读数变成两句可测的话：
1. **冻结长视野的每一个 case，t0 推导不出任何依赖边**（从任务表重算，不是从归档读）；
2. **规则是活的**：同一个 case、同一份 t0 世界，把一个"它自己该去的托盘"里的物体放进去、
   并对它要去的那个托盘拒绝一次放置，`derive()` 就写下了一条边（c2 走位移规则、c3 走容量规则，
   断言只要求"边存在且指名了被约束的区域"——哪条规则先答是 case 的性质，不是契约）。

**对 v0.5 的更正（写在这里，不改写封存报告）**：v0.5 §4 的 H1 说"模型在观测到……时写下
依赖边"。按上面的读数，**写边的是规则，模型与写边无关**；真正与模型有关的是"这一集有没有
活到能观测到那次位移"。RQ17 交付的条件触发率因此是**推导规则 × 存活到该轮**的联合条件率，
不是"模型的写边倾向"——H1 批的读法必须按这个更正执行（P4 前写进预登记）。

### 冻结面与回归（提交前当场跑）

- 三门：`2f1c74f52e91` / `23abe58ff333…` / `7df449ed2f4d` rc=0；
- `test_v02_contracts.py` 25 passed（fingerprint 逐项相等）；
- 全量回归 **1292 passed / 27 skipped**（v0.5 的 1283/27：**+9，无一条减少**；
  9 = Q1 契约 6 + H2 契约 3）。