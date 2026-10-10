# Continuous-Decision Embodied Agent v0.5 —— 阶段日志

执行纪律沿 v0.3/v0.4：**先预登记、先测量、后说话；判据进测试与仪器；每条读数带论域；负结果保留并给
原因；`cost_estimate_usd` 无单价时保持 `None`。** SPEC 是
`Continuous-Decision-Embodied-Agent-SPEC-v0.5.md`；读数（P4 之后）将记在 v0.5 最终报告。

v0.5 的两条新纪律（SPEC §4 原则 16–17）：**归因先于修复**（修复裁定输入是 A1 的证据链，
不是直觉；"顺手多修一个环"不在授权内）；**分析也是实验**（A1/A2 的判据与读法先落本日志
再开跑，跑完不回头改判据）。

---

## P0 预检（零成本，2026-10-10）

### 边界验证（当场重跑，未转引）

解释器：`/home/czx/miniforge3/envs/embodied/bin/python`（`embodied` conda 环境；
系统 `python3` 无 pydantic，三门在那里跑不起来——**这是环境事实不是代码事实**，记录在案）。

| 门 | 命令 | 输出 | rc |
| --- | --- | --- | --- |
| 冻结任务表 | `python -m embodied_agent.cli freeze --check` | `frozen list matches: 2f1c74f52e91` | 0 |
| 预注册清单 | `python -m embodied_agent.cli prereg --check` | `pre-registration matches the code: 23abe58ff33372ffa6f62a608221dfc1af2006f85ae50f7651a0f28451aae7b3` | 0 |
| em 集 | `python -m embodied_agent.cli em-pairs --check` | `em set matches: 7df449ed2f4d` | 0 |

三条哈希与 v0.4 报告 §0 表逐位一致（`2f1c74f52e91` / `23abe58ff333…` / `7df449ed2f4d`）。
契约冻结面：`tests/contract/test_v02_contracts.py` **25 passed**（`schema_fingerprint()` 与
`configs/experiment/v02_schema_freeze.json` 逐项相等的承载判据）⇒ v0.5 的三个落点
（R1 的 `core/runtime.py`、A1/A2 的离线仪器、E2'' 的驱动）**都不在 `core/v02.py`**，
§2.2 的冻结面约束成立。

`cli prereg --check configs/experiment/v04_e2_preregistration.json` 报
`self-inconsistent`（该文件的自洽规则哈希与自身记录不符）——**这不是 v0.5 的问题**：
`prereg --check` 的默认目标是 `p3_preregistration_v1.json`（v0.2/v0.3/v0.4 三阶段一直在跑
的那一份），逐阶段预登记文件（v03_*/v04_*）不是该命令的自洽检查对象。按 SPEC §2.3
"三门"字面执行，记录的是默认目标的 rc=0 与哈希；此条记在案上，免得日后被当成新缺陷。

### 残留处置引用（v0.4 报告 §8 的三笔账，v0.5 的入口账）

| # | v0.4 原文（摘要） | v0.5 的落点 | 本阶段不做的事 |
| --- | --- | --- | --- |
| 21 | blocked 终止的集 `failure_type`/`termination_reason` 均为 None，原因只在事件流里（#18 的集内表亲） | **R1（P1）**：`core/runtime.py` 的 blocked 路把决策自带的理由写上摘要面；SPEC §5 四条验收 | 不回填 E2' 归档里那四集的 None（§2.4 历史产物不回填） |
| 22 | "模型何时写依赖边"本身成了研究问题（触发率 1/34 且突发） | **A2（P2）**：交付触发假设 + 可测判据 + 最小验证设计（RQ12） | 不重开 E1' 的规模追加、不跑 A2 的验证批（SPEC §11） |
| 24 | c6 三决策源全灭（rule 10/10 确定性、模型席 6/6） | **不进 v0.5**；裁定权挂 D2''（§11） | 不处置 |

方向性事实（full-on-VLM 0/4，v0.4 §3 的判定"瓶颈是感知接口交给回路的世界"）在 v0.5
是散文级判定，**A1（P2）把它拆到环节上**（RQ11）。

### 本阶段的环境与工具事实

- 归档数据源（只读，SPEC §14）：`/home/czx/embodied-agent-batches/v04/{e1,e2,mem1_model,mem1_joined}/`
  盘上存在，`v04/e2/` 下三格 `long_horizon_{privileged,stub,vlm}` 与批摘要 `e2_prime_report.json` 就位。
- v0.4 仪器（`work/v04/*`）封存不改；v0.5 新仪器一律落 `work/v05/`。
- 工作树的 CRLF 噪声：Windows 侧 checkout 带 `core.autocrlf=true`，`git status` 会把 14 个
  内容零差异的文件标成 ` M`。**按内容为零差异处理，不提交它们**（每提交前用
  `git diff --stat` 自查，任何非零行数都要解释）。

**提交**：`Continuous-Decision-Embodied-Agent-SPEC-v0.5.md` + 本日志开篇。

---

## P1 R1（残留 #21：blocked 的原因上摘要面，零成本，2026-10-10）

### 先量后改：红的那一版

新契约测试 `tests/contract/test_v05_blocked_reason.py`（5 条）在**未改代码**上跑：

```
FAILED test_a_blocked_episode_states_why_on_the_result_object
  assert ep.result.termination_reason, "a blocked episode with a stated reason must say so"
  assert None = EpisodeResult(..., artifacts={..., 'note': 'blocked by model'})
FAILED test_a_silent_block_still_states_a_reason
  assert None == 'blocked by model'
2 failed, 3 passed
```

复现的正是 v0.4 残留 #21 的形状：**`failure_type=None`、`termination_reason=None`，而
`artifacts.note` 与事件流里已经写着 "blocked by model"**——原因在盘上，只是没有一张摘要
面看得见它。另外 3 条（clarify / 成功集 / `failure_type` 不动）在改动前就是绿的，
它们是"不回退"那一半的基线。

### 改动形状（SPEC §5，以实测为准）

盘上实测：`Decision` 契约里 blocked 自带的理由字段是 **`rationale`**（`missing_information`
按契约只在 `action=="clarify"` 时必填），`core/runtime.py` 的 `termination_reason` 在物理
后端**从来没有被写过**（只有 `benchmark/runtime_alfred.py` 与 `benchmark_mujoco/runtime.py`
两个子类在自己的 `_finalize` 里写它，用的是 SPEC-BST 6.2 的封口词表）。因此：

| 位置 | 改动 |
| --- | --- |
| `core/runtime.py` blocked 路 | 原因 = `decision.rationale.strip()`，空则回落常量 `BLOCKED_FALLBACK_REASON = "blocked by model"`（**命名模型的沉默，不替它编原因**） |
| 同上 | `terminated_blocked` 事件载荷新增 `reason`；`note`（守卫句"blocked 不证明任务不可解"）原样保留 |
| 同上 | `_finalize` 的 note 实参由硬编码 `"blocked by model"` 改为携带同一原因（→ `artifacts.note` 与 `episode_end`） |
| 类属性 | **新增 `blocked_reason`**，不是写 `termination_reason` |
| `failure_type` | 不动（仍 `None`）；**`FailureCode` 枚举未扩**，SPEC §2.2 的停工条款没有被触发 |

### 改动撞上的一处真实反作用（先记下来，它是这次改动里最要紧的一条）

第一版实现照字面"把原因写进 `termination_reason`"，红的不止新测试：全量跑出
`test_bst_text_backend.py::test_control_outcomes_seal_the_episode_at_once[blocked-AGENT_BLOCKED]`
——**ALFRED 文本后端的封口词表被覆盖了**。该后端在 `_finalize` 里
`if self.termination_reason is None: self.termination_reason = self._termination_of(...)`，
把 `failure is None` 封成 `AGENT_BLOCKED`；循环先把散文写进同一字段，封口就再也轮不到。

处置：**换字段而不是改后端**。循环写 `blocked_reason`（散文），`_finalize` 报
`termination_reason=self.termination_reason or self.blocked_reason`。于是两边各得其位：
物理后端（E2'/E2'' 跑的那条）没有封口词表，摘要面上就是决策自己的话；封口后端保住
`AGENT_BLOCKED`，散文仍在 `artifacts.note`、`terminated_blocked.reason` 与 `episode_end.note`
里。两侧各有一条测试钉住（`test_v05_blocked_reason.py` 与
`test_bst_text_backend.py::test_a_blocked_episode_keeps_the_seal_and_still_carries_its_reason`），
互为反面证据。**若当时只跑新测试，这条反作用会带进 v0.5 的正式批。**

### 验收逐条判定（SPEC §5）

| 条 | 判定 | 证据 |
| --- | --- | --- |
| 1 blocked → `termination_reason` 非空且与事件流一致 | **达成** | `test_a_blocked_episode_states_why_on_the_result_object`（事件 `reason` == 结果 `termination_reason` == `artifacts.note` == `episode_end.note`）；沉默版 `test_a_silent_block_still_states_a_reason` |
| 2 `failure_type` 保持 None（枚举不扩的行为面证据） | **达成** | `test_a_blocked_episode_keeps_failure_type_none`；`FailureCode` 一行未动 |
| 3 非 blocked 各路不回退（clarify 照旧带 `AMBIGUOUS_TASK`，v0.4 R1 账本覆盖判据原样绿） | **达成** | `test_clarify_still_carries_its_failure_code`；`tests/contract/test_v04_infra_ledger.py` 6 条原样通过；封口后端 `AGENT_BLOCKED` 绿（上面那条反作用） |
| 4 成功集不造假行 | **达成** | `test_a_success_states_no_reason_at_all`（`termination_reason is None`，`artifacts.note == ""`） |

**历史不回填**（SPEC §5 末条、§2.4）：E2' 归档那四集 blocked 的 `None` 保持原样，
答案由 v0.5 的新批给。

### 冻结面与回归（提交前当场跑）

- 三门：`2f1c74f52e91` / `23abe58ff333…` / `7df449ed2f4d`，rc=0 三条；
- `tests/contract/test_v02_contracts.py` **25 passed**（fingerprint 逐项相等）——
  `core/runtime.py` 不在 `core/v02.py` 的哈希面上，预期内，实测确认；
- 全量回归 **1275 passed / 27 skipped**（v0.4 基线 1269/27：**+6 条，无一条减少**，
  6 = v0.5 新增 5 + 封口后端新增 1）。