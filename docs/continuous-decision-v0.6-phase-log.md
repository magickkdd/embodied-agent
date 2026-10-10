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