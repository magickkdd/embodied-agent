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

---

## P2 A1 判据（先于任何读数落盘；2026-10-10，SPEC §6 / RQ11）

**分析也是实验**（SPEC §4 原则 17）：本节落盘时，A1 的仪器尚未运行，本节的任何读法
不得因结果而改。仪器落 `work/v05/`，输入清单载明归档路径与 commit。

### 输入清单（只读，SPEC §14）

| 源 | 路径 | commit / 身份 |
| --- | --- | --- |
| E2' 归档（三通道 × 2 case × 2 repeats = 12 集） | `/home/czx/embodied-agent-batches/v04/e2/long_horizon_{privileged,stub,vlm}/<run_id>/` | run_id `…20260930_130138` / `…130206` / `…130350`；`e2_prime_report.json` |
| 逐集产物 | `episodes/<episode_id>/{events.jsonl,episode_summary.json,model_calls.jsonl,perception/}` | 同上 |
| 冻结任务表 | `configs/experiment/frozen_long_horizon_v1.json` | sha `2f1c74f52e910073`（与三格 `task_manifest.json` 一致） |
| 键名清单（仪器的前置勘察，非分析） | `work/v05/a1_keys.py`、`a1_keys2.py`、`a1_keys3.py` 及各自 `*_output.txt` | 本仓库，落 `work/v05/` |

**适用域**：只覆盖 E2' 这 12 集与这三个通道的配置（读侧 = StubReader / VLMReader(agnes-2.5-flash,
`s2-perceive-v1`)，决策器 = rule policy，`grounding_map_sha256` c1 `772f28bf…`、c3 `e889af9a…`）。
不外推到 v0.3 的 E2（桥与读侧都变过）。

### 测量单位与数据源（每格一句）

- **声明项**：该集 `episode_summary.goal_resolution.assignments`（共享目标解析，三通道同
  `(case, repeat)` 下逐项相同 ⇒ 跨格可比）。每项 = `(color, shape) → target`。
- **轮**：`decision_context` 事件（`round_index` / `state_version` / `progress` / `candidates`）。
- **帧**：vlm 通道 = `perception` 事件的 `detections`（含 `state_attributes.color/shape`、
  `how_identified`）与 `model_calls.jsonl` 的 `raw_response` / `finish_reason` /
  `format_repairs_this_call`；stub 通道**没有 `perception` 事件**（`perception_events: 0`），
  故其帧端读数由**离线确定性重放** `StubReader` 于归档的 `perception/look_*.png` + `.depth.npy`
  得出（零请求、可复现、不写归档）；privileged 通道不走相机，帧端一栏记 `n/a`。
- **接地后的世界**：归档里没有 `WorldState` 行，**以决策上下文的 `progress` / `candidates`
  为回路实际看到的那份**（这是回路自己的读法，不是替它重建一个）。

### 四个环的判据（逐项、逐集判定；先判定，后归因）

| 环 | 问什么 | 测量 | 判定（非零即该环有贡献） |
| --- | --- | --- | --- |
| **a 帧端检测** | 这一帧有没有看到该项的**颜色** | 该帧 detections/stub 重放里存在 `color == 声明 color` 的检测 | **该项在全集帧上都没有该颜色的检测** ⇒ 该项归 a。偶发漏检不归 a（一次抖动不等于一个死因，判"全集"是预登记的门槛） |
| **b 接地/绑定** | 看到了之后，绑定成了回路可行动的名字吗 | 逐轮 `progress` 中该声明项是否 `unmeasured` 含 `entity_binding`；该项是否进过 `candidates` | 出现过"未绑定轮" ⇒ b 有贡献。分两个子式（由证据定，不预设）：**b-1 失配**（该帧的检测颜色存在但 `shape` 与声明不符，属性匹配 0 命中）/ **b-2 歧义**（多个实体同属性，匹配 >1 命中） |
| **c 决策可用性** | 名字有了以后，决策器还能动吗 | 逐轮 `candidates` 中该项是否有可行动作；`decision` 动作序列；`execution_feedback` 的 `status`/`failure_code`/`rejection_reasons`；终止形态与 `identical_*` 计数 | 全部声明项都至少一轮可行动，且在合法动作之后仍以 blocked / REPEATED_INVALID / BUDGET_EXHAUSTED 终局 ⇒ c 独占该集；否则 c 只对"已绑定却始终不可行动/动作无效"的项有贡献 |
| **d 提示结构（仅 vlm）** | 帧端读数是不是被提示或解析坏掉 | 逐请求：`ok`、`finish_reason`、`format_repairs_this_call`、`schema_errors`、`raw_response` 可解析性、返回 `objects` 的 `color`/`shape` 是否落在 catalog 词表、`absent` 列表 | 某请求解析失败/词表外 ⇒ d 对**该帧**有贡献；整集无一次解析失败 ⇒ d 对该集贡献 0（失败一律记名，不记"大概"） |

### 归因规则（预登记，跑完不改）

1. **逐项归因**：按 a → b → c 的因果次序取**第一个非零环**为该项的主导环；d 只在 a 判零
   而同帧的检测缺失时才有贡献（d 的失效在下游表现为 a 的漏检，这是它能被看见的唯一路径）。
2. **逐集主导环**：该集内**受影响项最多的环**；并列时取因果序在前者。
3. **分环贡献表**：每环的"受影响项数 / 集数"，**允许多环并存**（SPEC §10 风险 1：多环不是
   失败，是读数）。"瓶颈是 VLM"的判定必须先过"stub 同样死"这一关（SPEC §6）。
4. **对照组**：privileged 4/4 是同一决策器在无相机条件下的对照；stub 与 privileged 的差隔离
   "相机 + 限定语义"面，vlm 与 stub 的差隔离"VLM 感知"面。

### 读法（防止把读数读成结论）

- 交付形态 = **瓶颈环判定 + 每集证据链 + 分环贡献读数**；每集一行，逐项一行。
- 全部计数带论域（哪一格、哪几集、哪几个 case）；不跨格平均。
- 任何"因为 A 所以 B"的句子，必须能在证据链里指到那两行。
- 花费 **0 请求**（归档读取 + 离线确定性重放）。`cost_estimate_usd` 保持 `None`。

### 仪器（落 `work/v05/`，可复现）

- `a1_keys.py` / `a1_keys2.py` / `a1_keys3.py`：键名与内容勘察（**输入清单，非分析**）；
- `a1_attribute.py`：按上表逐项测量的唯一读数仪器，输出 JSON + 逐集表；
- `a1_stub_replay.py`：stub 帧端离线重放（a 环数据源），被上表调用；
- `a1_evidence.py`：从 `a1_attribute.json` 里挑出"有过未绑定轮"的项，打印逐轮证据链
  与模式计数（报告里引用的证据行由它复现）；
- 二者均**只读归档**，产物写 `work/v05/`（SPEC §14：分析仪器不得写归档目录）。

---

## P2 A1 读数（2026-10-10 当场跑，判据见上节，跑后未改判据一字）

### 开跑前仪器自身的两处改正（先记，否则下面的数不可信）

第一版 `a1_attribute.py` 与判据**不一致**，两处，都在**任何读数产生之前**改掉：

1. 判据的 a 环门槛是**全集**（"该项在全集帧上都没有该颜色的检测"），仪器第一版却按
   **逐轮**判，把偶发漏检也算成 a 环的贡献 ⇒ 会把 a 环虚增。改为项级判定，并另设
   `rounds_frame_missed` 一列如实记录偶发漏检（读数不因门槛而消失）。
2. 判据的 c 环有**集级**那半句（"全部声明项都至少一轮可行动，且在合法动作之后仍以
   blocked / REPEATED_INVALID / BUDGET_EXHAUSTED 终局 ⇒ c 独占该集"），仪器第一版只实现了
   项级那半句 ⇒ 会把 c 环虚减。补上 `ring_c_episode`。

改的是仪器，不是判据。改完再跑。

### 逐格逐集读数（匹配分母 4/格；`work/v05/a1_attribute_output.txt` 为全文）

| 通道 | 集 | 终局 | 完成 | 主导环 | a | b | c | d | `c_episode` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| privileged | c1 r0/r1 | success | 4/4 | **无**（四环全 0） | 0 | 0 | 0 | 0 | false |
| privileged | c3 r0/r1 | success | 6/6 | **无**（四环全 0） | 0 | 0 | 0 | 0 | false |
| stub | c1 r0 | REPEATED_INVALID | 1/4 | **b** | 0 | 1 | 0 | 0 | false |
| stub | c1 r1 | REPEATED_INVALID | 1/4 | **b** | 0 | 1 | 0 | 0 | false |
| stub | c3 r0 | blocked | 1/6 | **b** | 0 | 4 | 0 | 0 | false |
| stub | c3 r1 | blocked | 1/6 | **b** | 0 | 4 | 0 | 0 | false |
| vlm | c1 r0 | BUDGET_EXHAUSTED | 0/4 | **b** | 0 | 2 | 0 | 0 | **true** |
| vlm | c1 r1 | BUDGET_EXHAUSTED | 0/4 | **b** | 0 | 1 | 0 | 0 | **true** |
| vlm | c3 r0 | blocked | 1/6 | **b** | 0 | 3 | 1 | 0 | false |
| vlm | c3 r1 | blocked | 1/6 | **b** | 0 | 3 | 0 | 0 | false |

**瓶颈环判定（RQ11 答卷）：b 环（接地/绑定），8/8 死集全部命中**。a 环按全集门槛 0/8；
d 环 0/8（vlm 三格共 92 次请求：`ok=True` 92、`finish_reason=stop` 92、`format_repairs=0`、
`schema_errors=0`、`raw_response` 不可解析 0 次、词表外属性 0 次——**提示面与解析面本批无故障**）。

### b 环内部的两种形态（逐轮模式计数，`a1_evidence.py`）

| 形态 | 含义 | 出现（有过未绑定轮的项，逐轮） |
| --- | --- | --- |
| `shape_mismatch` | 帧端**看到了这个颜色**，但它报的 `shape` 与声明不符 ⇒ 属性匹配 0 命中 | **22**（stub 11 / vlm 11） |
| `frame_did_not_see_the_colour` | 该帧没有这个颜色的检测 ⇒ a 环的**间歇**形态 | 38（stub 25 / vlm 13） |
| `ambiguous_after_binding` | 绑定后多个实体同属性 ⇒ 匹配 >1 | **0** |
| `unbound_with_a_unique_match` | 唯一命中却仍未绑定 | **0** |

两种形态都落在同一句话上：**该项在那一轮从"回路可行动的世界"里静默消失了**——`progress`
里留一行 `value=unknown` + `unmeasured=["entity_binding"]`，`candidates` 里没有它，
决策器看不见它、也没有人报错。

### 两条最干净的逐集证据链（`work/v05/a1_evidence_vlm.txt` / `_stub.txt` 可复现）

1. **vlm / c3 / item0 黄色方块**：`{'shape': 'cube', 'color': 'yellow'}` → 声明 `obj_yellow_1`。
   7/7 轮、4/4 轮里**帧端都看见了黄色**（检测为 `['yellow', 'cuboid']`，两次 repeat 完全一致），
   但它报的是 **cuboid**，声明要的是 **cube** ⇒ `bound 0/7`、`actionable 0/7`、
   `mode=shape_mismatch`。**一个词的形状分歧，把一件物体从回路的世界里删掉了**，直到预算耗尽。
   同一格里另外五个项（绿圆柱、紫方块、红长方体、蓝方块、黄长方体）都能行动——
   **不是整格都瞎，是这一件看不见**。
2. **stub / c1 / item3 紫色圆柱**：前 3 轮检测为 `['purple', 'cuboid']`（声明 cylinder）⇒
   `shape_mismatch`；后 3 轮紫色**整段从分割里消失** ⇒ `frame_did_not_see_the_colour`。
   `bound 0/6`、`actionable 0/6`。而这一集真正的终局形态（REPEATED_INVALID）来自另一条线：
   绿方块的 6 次 `pick` 里 4 次 `IK_OR_PATH_UNREACHABLE`，于是"相同动作 + 无新证据"的守卫触发。

### 分环贡献读数（跨 8 个死集、40 个项-集）

| 环 | 贡献的项数 | 贡献的集数 | 备注 |
| --- | --- | --- | --- |
| a 帧端检测 | **0**（全集门槛） | 0 | 间歇形态 38 个项-轮，**不作归属**，单列 |
| **b 接地/绑定** | **19**（stub 10 + vlm 9） | **8** | 唯一命中 8/8；v0.4 的"感知接口是瓶颈"落到了具体一行代码的契约上 |
| c 决策可用性 | 1（vlm c3 r0 的红长方体：已绑定 2/7 却 `actionable 0/7`）+ **集级 2**（vlm c1 ×2） | 3 | 集级那两集里，每一项都曾经可行动 |
| d 提示结构 | 0 | 0 | 92/92 请求干净 |

### 差分设计的两道门（SPEC §6）

- **"stub 同样死"这一关**：过了，而且死法相同——stub 两格的主导环也是 b，成因同样是
  形状声明与帧端形状的失配（`['purple','cuboid']` 对 cylinder、`['yellow','cylinder']` 对 cube、
  `['green','cuboid']` 对 cylinder）。
  ⇒ **"瓶颈是 VLM"这个说法在 v0.5 的证据下不成立**：把 VLM 换成确定性分割器，
  同一个环照死不误。可立的是"**瓶颈是绑定契约**"，不是"瓶颈是读侧模型"。
- **privileged 对照**：4/4，四环全 0，同一决策器、同一冻结集、同一目标解析。
  ⇒ 排除决策器（v0.4 §3 的散文判定第一次有了逐项对照）。

### 这条判定**不**说什么（论域）

- 只覆盖 E2' 这 12 集、两个 case、两次 repeat；不外推到 c2/c4/c5/c6，不外推到 v0.3 的 E2。
- `bind_attributes` 的"恰好一个命中"分支（歧义）在本批**一次都没走到**：c3 两黄在 v0.4 R3
  的复合键下分得开，所以歧义没被触发——**这条分支的死法本批无读数**，不得当作"没问题"。
- 间歇漏检（38 个项-轮）是真实贡献，按预登记门槛不归属给 a 环，但**修 b 环不会自动修它**；
  P3 的修复若只处理形状失配，读数应当仍然是 0/N——这一点在预登记里写死（见 P3）。

---

## P2 A2 判据（先于任何读数落盘；2026-10-10，SPEC §6 / RQ12）

**本节落盘时，A2 的仪器尚未运行。**交付物是**假设 + 判据 + 最小验证设计**，不是率、不是结论
（SPEC §6 的诚实条款）。

### 语料与触发的定义

| 项 | 值（判据写死） |
| --- | --- |
| 模型席语料 | v0.4 E1' `/home/czx/embodied-agent-batches/v04/e1/long_horizon_full/`（3 个 run，模型席 34 集）+ v0.3 E1 `/home/czx/embodied-agent-batches/v03/e1/long_horizon_full/`（模型席 153 集）= **187 集**；**rule 席与消融席不进语料**（v0.4 的 rule 席 60 集结构性 0 触发，是定义上的 0，不是观测） |
| 触发 | 某集存在 **≥1 条被写下的依赖边**（任一 plan 视图事件的 `dependencies` 非空）——与 shipped 记分器 `evaluation/long_horizon.py` 的 L2 分母同一定义；**仪器必须复现记分器看到的同一条边集合**（判据：同一集上仪器的 `dependency_edges` 与 `lh_score/*.json` 的 `detail.dependency_edges` 逐项相等） |
| 分母 | 每集一次；每边一次；两个分母都记 |

### 读法（n=3 的诚实条款，逐条写死）

1. **不出率、不出结论**。3 个触发集只能支持"假设生成"；
2. **任何共变都必须两侧都数**：触发集的协变**与非触发集的同一协变**并排，3 vs 184 也要写；
3. 每个假设必须写全三件：**协变量名**（事前枚举，不得事后新增）、**可测判据**（能被读数
   判定真假的可观测量）、**最小验证设计**（最小集数 / 干预什么 / 读什么）；
4. 若事前枚举的协变量在盘上**没有任何可区分的观测量**，交付具名负读数
   **"触发机制在现有语料上不可归因，需干预式设计"**（SPEC §10 风险 4），不是沉默；
5. 每条读数带论域（哪个 run、哪个席、哪个 case），不跨 run 平均。

### 事前协变量清单（**在读触发集内容之前**写定；仪器按此逐项填表）

| # | 协变量 | 可观测量 |
| --- | --- | --- |
| V1 | 席位身份 | 该集 manifest 的 `model.provider` / `model.model` |
| V2 | run / 块序 | run 目录时间戳与 run 序号 |
| V3 | 场景 | `case_id`（frozen long_horizon 的 6 个 case） |
| V4 | 触发所在的决策轮位 | 触发 plan 视图事件的 `round_index`（缺则记 None） |
| V5 | 触发前的失败历史 | 触发事件之前 `execution_feedback.failure_code` 非 none 的条数、拒绝条数 |
| V6 | 触发边是否被违反 | 该边的 `violated` 字段 |
| V7 | 触发前是否有恢复动作 | 触发之前 `recovery_action` / `plan_revision` 的条数 |
| V8 | 环境扰动是否触发 | 该集 summary 的 `environment_events.fired` 条数 |
| V9 | 该集结局 | `outcome` / `failure_type` |
| V10 | 该集轮数 | `decision_rounds` |

### 仪器（落 `work/v05/`）

- `a2_scan.py`：扫全部模型席集，产出每集的"是否触发 + 边集合 + 上述 10 项协变量"的表
  （触发集与非触发集同表，不分开存）；
- `a2_check_scorer.py`：把仪器在 v0.4 E1' 34 集上算出的 `dependency_edges` 与
  `lh_score/long_horizon_v0.json` 逐项对账（上面那条判据的实现）；
- `a2_corroborate.py`：v0.3 E1 的两个触发集定位（路径与 commit 落输入清单）。

### 开跑前三处改正（仪器对判据；判据未动）

1. **语料路径写错了一格**。判据表里写的 `v03/e1/long_horizon_full`（153 集）只装了 12 集；
   `a2_cells.py` 逐格数出 153 = 6 个 `long_horizon_*` 格（63）+ 6 个 `em_*` 格（90），
   12 个格全是 `planner=deepseek` 的模型席；`vlm_contrast`（rule 席 94 集）与 v0.4 的
   `long_horizon_full_rule`（60 集）不入语料。判据的**数**（187）没错，错的是路径。
2. **两侧不可比的计数器**。第一版仪器对"触发前"的四个计数只在遇到第一条边时停下，
   于是在 184 个未触发集上，同一列悄悄变成了**全集**计数——两侧量的不是一回事。
   改成两本账：`whole_episode`（187 集同规则，协变量表用它）与
   `before_trigger`（只对触发集有意义）。**改的是仪器**；改前的 V5/V7 两行读数作废。
3. **`violated` 是字符串**（`"False"`）。`bool()` 会把三条边全判成违反；改为显式解析。
   结论未变（三条边在后续视图里确实转为违反，见下），但 V6 的语义从"写下即违反"变成
   "最终被违反"，与记分器 L2 的分子一致。

### 语料与触发（`a2_scan.py`）

| 源 | 模型席集数 | 触发集数 |
| --- | --- | --- |
| v0.3 E1（12 个 `planner=deepseek` 格） | **153** | **2** |
| v0.4 E1'（`long_horizon_full` 3 个 run：agnes×2 + sensenova×1） | **34** | **1** |
| 合计 | **187** | **3** |

**与 shipped 记分器对账**：v0.4 E1' 34 集上，仪器算出的 `dependency_edges` 与
`lh_score/long_horizon_v0.json` 里逐集的 `detail.dependency_edges` **逐项相等（34/34，0 不符）**，
触发计数 1 与 v0.4 报告的 1/34 一致（`a2_check_scorer.py` 输出 `OK`）。

| # | 触发集 | 席 | 结局 | 写下边的视图 | 边的 `kind` | 最终 `violated` |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | v0.4 `lh_c2_displaced_completion.B.r0` | agnes | failed / REPEATED_INVALID | v2（`new_observation`） | recovery | 是 |
| 2 | v0.3 `lh_c1_shared_pair_restore.B.r0` | agnes | success | v3（`new_observation`） | recovery | 是 |
| 3 | v0.3 `lh_c2_displaced_completion.B.r1` | agnes | failed / MODEL_ERROR | v2（`new_observation`） | recovery | 是 |

### 三条边的事件序列（`work/v05/a2_trigger_views.txt` 与逐视图核对）

三个集的形状**完全同构**：`v1`（`trigger=initial`）无依赖边 → 某一版重规划视图**首次写下**
一条 `kind=recovery` 的边（当时 `satisfied="True" violated="False"`）→ 之后的某一版视图
`trigger=dependency_violation`，同一条边变 `violated="True"`，之后各版一直带着。

模型自己写下的理由是同一句话的三个实例：

> `obj_green_5 was displaced out of tray_left to let obj_blue_1 in and must be restored before the task ends`

### 两侧协变量表（`a2_covariates_output.txt`；事前枚举的十项，一项未增）

| 协变量 | 3 个触发集 | 184 个未触发集 | 有分辨力吗 |
| --- | --- | --- | --- |
| V1 席位 | agnes 3 | agnes 172 / sensenova 12 | **无**（3/172 vs 0/12，n 太小） |
| V2 run | v04#0 ×1、v03 的 full 格 ×2 | 每个 run 11–16 | **无** |
| V3 case | c2 ×2、c1 ×1 | c5 18 / c6 17 / c3 16 / c1 15 / c2 13 | **无**（能位移的 c1/c2/c3/c6 共 64 集，只有 3 集触发） |
| V4 视图版本 | 2、3、2（**无一是 v1**） | 187 个初始视图全部无边 | **有**（见 H2） |
| V5 失败数（全集） | 8、4、6 | 0–7，众数 0–1 | **无** |
| V6 边最终被违反 | 3/3 | 无边可比 | 不可分（条件量） |
| **V7 `recovery_action`（全集）** | **13、11、6** | 133 个为 0，**最大 5** | **有**（3/3 高于其余最大值，差 **1** 次事件） |
| V8 环境事件触发数 | 1、1、1 | 0（91）/1（76）/2（17） | 无 |
| V9 结局 | success 1 / failed 2 | success 155 / failed 24 / clarify 5 | 无 |
| V10 决策轮数 | 29、24、20 | 众数 7–8，最大 21 | **部分**（21 轮的未触发集压过 20 轮的触发集） |

**因果方向的诚实警告**：触发前的 `recovery_action` 计数在三个触发集上都是 **0**
（边写在第 2–3 版视图，此前没有任何恢复动作）。全集计数（6/11/13）之所以高，
很可能是**写边之后**的义务驱动了后续恢复，而不是恢复驱动了写边。⇒ V7 的**相关**成立，
**因果方向未定**。

### 假设清单（RQ12 交付：假设 + 判据 + 最小验证设计；不是率，不是结论）

**H1（内容假设，后验生成，判据先写）**：模型在**观测到"自己已放好的东西被另一个放置挤出去"**
时写下 `recovery` 依赖边——三条边的 `note` 都是这个句式，而 c1/c2/c3/c6 都声明了
`place` 后的 `impulse` 扰动。
- **可测判据**：在有位移扰动的格里，"本集出现过已放置物被挤出托盘"的子集里，
  边触发率显著高于"未出现该观测"的子集；且触发集的边 `note` 含位移语义。
- **最小验证设计**：干预式——同一冻结集、同一席位，**两格 ×12 集**：
  格 A = c2（位移可观测），格 B = c3（同样有 `impulse`，但语义不同）；
  只在"确有该观测"的集上读条件触发率。上界 ≈ 24×31.1×1.25 ≈ **930 请求**（免费层）。
  读法预写死：0 触发 ⇒ rule-of-three 上界 3/24 = 12.5%，判"H1 在该条件下不必然"。

**H2（视图版本假设，事前 V4）**：依赖边只出现在**重规划**视图，**从不**出现在初始视图。
- **判据**：187 集的每一个 `trigger=initial` 的视图，其 `dependencies` 恒为空
  （现有语料 187 个初始视图、0 个反例，零成本可复算）。
- **最小验证设计**：零成本；把它写成一条契约测试（"初始计划视图不得携带依赖边"）
  是 v0.6 的输入。

**H3（恢复区共变假设，事前 V7）**：写边与"该集进入了持续恢复区"共变（全集计数 6/11/13
高于其余 184 集的 5），但**方向未定**（触发前的恢复计数为 0）。
- **可测判据**：在**恢复计数被干预**的条件下，边触发率随恢复计数单调上升；
  若恢复计数高而边仍不出现 ⇒ 证伪"恢复区充分"。
- **最小验证设计**：同 H1 的两格批；读数按 `recovery_action` 计数分层（预写死分档：
  0 / 1–3 / ≥4），每档的边触发率与 Wilson 区间。

**H4（边形态假设）**：触发集的边全部是 `kind=recovery` 且最终全部被违反；
语料里没有第二种 `kind`、没有一条边是在初始视图里写的。
- **判据**：同上，属现有语料上的读数；**n=3 不能排除"别的 kind 只是没出现"**，
  不得写成"模型只会写 recovery 边"。

### 具名负读数（SPEC §10 风险 4 的那一格）

**触发机制在席位 / run / case 三个维度上不可归因**：三项协变量在 3 vs 184 的语料上都没有
分辨力（各项的取值分布见上表）。这不是"没有发现"，是**在这份语料上不可归因**，
要归因必须换设计（H1/H3 的干预批），而不是加集数——按 v0.4 的实测率 1/34，
"两位数触发"需要 ~680 集、约 26,000 请求，本阶段任何可负担规模都到不了。

---

## P3 修复裁定与 E2'' 预登记（2026-10-10）

### 用户裁定（记于 SPEC §13）

| # | 裁定 |
| --- | --- |
| D1'' | 归因 + 非零，按 SPEC 执行 |
| D2'' | #24（c6 三决策源全灭）**不进 v0.5**，按 §11 默认；重冻结级决定留给下一阶段 |
| D3'' | **`FailureCode` 枚举不扩**（R1 实测 `termination_reason` 足够，未触发 §2.2 停工条款）；**修复只改目标侧绑定**，读侧与决策策略明确不修 |
| D4'' | 照 §7：E2'' = 165 请求 / 12 集 / 3 格，匹配分母 4；不需要第二批 |

### 缺陷的一行陈述（A1 的证据链落到这里）

同一个问题——"这条声明指向哪件物体"——盘上有**两套规则**：

- `GroundingMap._lookup`（`perception/grounding.py:185`）写明：*"a unique colour wins whatever
  the shape says — a misread shape must not override the bridge"*；
- `RuntimeVerifier.bind` → `bind_attributes`（`core/verify.py`）要求帧端**实测**的每个属性与声明
  逐项相等、且恰好一个实体命中。

更严的那套恰好用在了决定结果的地方，于是读侧一次形状误读就把物体从回路的世界里撤回。
A1 的两条最干净证据链（vlm c3 的黄方块 7/7 轮被读成 cuboid；stub c1 的紫圆柱 3/6 轮读成
cuboid）就是这条规则的后果，不是读侧的"能力不足"。

### 改动形状（D3''：一个环、一条规则）

| 位置 | 改动 |
| --- | --- |
| `core/verify.py` `RuntimeVerifier.__init__` | 新增可选 `gmap`（特权通道为 `None`，行为不变） |
| `core/verify.py` `RuntimeVerifier.bind` | **先问桥**（`gmap.bind(color, shape)`），且答案必须**当轮可见**（`world.has_entity`）；旧的属性匹配降级为回落 |
| `core/verify.py` `bind_attributes` | 一行未动（回落路径 = 特权通道的全部行为） |
| `perception/verify_percept.py` `PerceptVerifier.__init__` | 透传 `gmap` |
| `perception/arm.py` `PerceptRuntime._verifier` | 把 `self.gmap` 交给 verifier |
| `core/planner.py` `RulePlanner` / `evaluation/sources.py` `RulePolicySource` / `evaluation/run.py` `make_source` | 同样把桥传下去——**否则修复到不了决策侧**：`pending_assignments` 自建 verifier，不传桥的话 `context.progress` 与"待办列表"会各说各话 |
| `perception/grounding.py` | **一行未动**（digest 与 `key_of` 逐字节不变，契约测试钉住） |

**没有动**（§4.16 的授权边界之外）：读侧阈值与提示词、`RulePlanner.decide` 的策略、
`FailureCode`、事件类型、世界契约、接地图本身。

### 契约测试先红后绿（`tests/contract/test_v05_goal_binding.py`，8 条）

红的那一版：`5 failed, 2 passed`（`RuntimeVerifier.__init__() got an unexpected keyword argument
'gmap'`；另 2 条是"不许多修"的护栏，改动前即绿）。绿：`8 passed`。

四条护栏各自钉一件事：**不得复活帧没看见的物体**（那是 a 环）、**不得用错误形状劈开歧义颜色**
（v0.4 R3 的拒绝要收窄不消失）、**特权通道逐字节不变**、**桥本身不变**。

### 一处真实的反作用，当场记、修法当场定

全量回归抓出 `tests/contract/test_v02_acquisition_arm.py::test_one_camera_episode_carries_the_perceiver_the_store_and_the_library`
由绿转红。查明（把产品代码 stash 掉跑同一集，前后各一次）：

| | 修复前 | 修复后 |
| --- | --- | --- |
| `dev_c1` @ stub 相机通道 | 绿圆柱**7/7 轮未绑定**（`{'shape': 'cylinder', 'color': 'green'}` + `entity_binding`）→ `failed/INVALID_DECISION` 2/3 → 触发 gap → 采集臂写下四条记录 | **success 3/3**，7 轮 0 请求 → 没有失败 → 没有 gap |
| 该契约测试的红点 | — | `assert set(OWNED) & set(types), "the acquisition arm filed none of its records on a camera"` |

**这条红不是缺陷，是修复起作用了**：零花费的一个相机集从"绑不上而失败"变成 3/3 成功。
但它也暴露一件该修的事：**那条断言原本靠"循环恰好做不好这件任务"才成立**——
测试的主体是"相机通道上的采集链"，前提却是涌现的失败。
处置（不是放宽断言）：`_camera_arm` 新增一个 `execute` 接缝参数，测试用
`_always_fails()` 在**执行器**上强制一次真实失败，让 gap→candidate→validation→refusal
四段链照旧被完整测到；断言一条不减，另加一句"事实本身也是断言"（本集现在成功）。
同族纪律：**判据不该依赖涌现的失败**。

### 全量回归（提交前当场跑）

- `1283 passed / 27 skipped`（v0.4 基线 1269/27 → P1 后 1275/27 → 现在 1283/27；
  **+8，无一条减少**）；
- 三门 `2f1c74f52e91` / `23abe58ff333…` / `7df449ed2f4d` rc=0；
- `test_v02_contracts.py` 25 passed（fingerprint 逐项相等；本轮未碰 `core/v02.py`）。

### E2'' 预登记（`configs/experiment/v05_e2_preregistration.json`）

SPEC §7 的三样前提逐项对上：A1 瓶颈环判定已落盘 ✅、D3'' 裁定已落本日志 ✅、
修复契约测试先红后绿 ✅。

- **规模**：3 格 × 2 case × 2 repeats = 12 集，匹配分母 4/格；privileged/stub 两格零请求；
- **上界**：165 请求（E2' 实测 132 × 1.25），免费层，`cost_estimate_usd: null`，
  `pricing_configured: false`；
- **身份声明**：接地图**未改**（c1 `772f28bf…`、c3 `e889af9a…` 与 E2' 同值，契约测试钉住），
  改的是回路**怎么用**它 ⇒ 身份不变、行为变 ⇒ 与 E2' **并排报告、不合并**（§2.5 的延伸）；
- **写死的预期**（跑前）：颜色唯一的项未绑定轮数应当**归零**；c3 两黄的歧义绑定与 38 个项-轮的
  间歇漏检**不会**被这次修复带走，所以三格仍可能读出 0——那是合法答案，前提是"归因环已修"的
  证据到位（机制检查写进验收条目：逐项 `entity_binding` 计数与 E2' 并排）；
- **验收条目**另含：blocked 集必须带非空 `termination_reason` 且与事件流一致（P1 的账在正式批上
  再结一次）、privileged 仍是 4/4 且动作序列与 E2' 同形（冒烟）、两账本合账对上界。

---

## P4 E2'' 正式批（2026-10-10，预登记 `configs/experiment/v05_e2_preregistration.json`）

### 探针判据（先于第一个请求落盘；SPEC §7 "探针先行"、§4 原则 15）

仪器：`work/v05/probe_seats.py`（v0.4 P2 脚本的逐字副本；SPEC §14 要求 v0.5 新仪器落
`work/v05/`，探针逻辑一字未改）。**本节落盘时尚未向任何端点发出第一个请求。**

E2'' 只需要一把席：视觉席 `configs/models/agnes-vision-r4.yaml`（`LLM_API_KEY`，免费层）。
决策来自 rule 策略，不占席——这一点与 E1' 不同，也是本次探针面比 v0.4 窄的原因。

| 探针 | 对象 | 判据（事先写死） | 花费 |
| --- | --- | --- | --- |
| A 席位健康 | `agnes-vision-r4.yaml` | 配置可读（零花费）+ key 可装载（零花费，只记变量名与长度）+ **1 次**最小请求 `raw_chars > 0` ⇒ 健康；0 字符或异常 ⇒ 停批并记账 | 1 |
| B 限流窗口 | 同上 | **10 次**最小请求、间隔 1 s；429/额度拒绝的次数与间距**是读数不是判决**（供上界与停止规则）；**连续 3 次拒绝 ⇒ 停批**（v0.3 §8 停止规则原文） | 10 |
| C 真实载荷资格 | —— | **本轮不设**：E2' 的 vlm 格已实测 23 次生产形状的视觉请求（prompt ≈1.4k tokens、completion ≈455、`finish_reason=stop`、2 次死于 429 限流而非形状），E2'' 本身就是同形状的载荷复测；按 D6' 的教训，此处再加一次"合格性"探测只会用小载荷低估预算 | 0 |

合计 ≤ **11 次请求**，全部免费层。读数不改判据。

### 三门的当场复核（第一个请求之前）

`freeze --check` → `2f1c74f52e91`；`prereg --check` → `23abe58ff333…`；`em-pairs --check` →
`7df449ed2f4d`；三条 rc=0（与 §0 同一批哈希）。

### 探针读数（2026-10-11 00:47 当场跑，判据见上，跑后未改判据一字）

| 探针 | 读数 | 判定 |
| --- | --- | --- |
| A 席位健康（`agnes-vision-r4.yaml`） | key 可装载（`LLM_API_KEY`，长度 51，值从不打印/存储）；最小请求 `raw_chars=12`、`finish_reason=stop`、0.53 s、无推理 token | **健康**（判据满足） |
| B 限流窗口 | 10 次：9 成功、**1 次 429**（第 10 次，重试 5 次全 429，15.5 s） | **读数**：与 v0.4 P2-D 同形（免费档突发限流）；**连续 3 次拒绝的停批规则未触发** |
| C 真实载荷资格 | 本轮不设（判据里已写明理由：E2' 的 23 次生产形状请求即先例，E2'' 是同形状复测） | — |

合计 **11 次请求**（免费层）。产物 `work/v05/probe_agnes_vision.json`（无凭据）。

### E2'' 正式批读数（2026-10-11 00:49–01:02，预登记 `v05_e2_preregistration.json`）

产物 `/home/czx/embodied-agent-batches/v05/e2/`，驱动 `work/v05/e2_batch.py`，
批摘要 `e2_double_prime_report.json`。**148 / 165 请求**（上界 90%），三格 rc：0 / 0 / **4**。

| 格 | 成功 | 失败形态 | 集数 | 请求（做出/归属） | `entity_binding` 未绑定行 | 与 E2' 并排 |
| --- | --- | --- | --- | --- | --- | --- |
| privileged | **4/4** | — | 4 | 0 / 0 | 0 | 4/4，动作序列逐轮同形（11/11/13/13） |
| stub | **0/4** | c1 两集 REPEATED_INVALID（1/4）；c3 两集 blocked（1/6） | 4 | 0 / 0 | **16**（E2'：36） | 0/4 |
| vlm | **0/4** | c1 r0 blocked（**1/4**）、c1 r1 **infrastructure_error（429 配额死，无摘要）**、c3 两集 BUDGET_EXHAUSTED（0/6） | 4 | 148 / 114 | 26（E2'：24） | 0/4 |

### RQ13 的答案：**仍然是 0**——但这是"归因环已修"之后的 0（合法答案的证明如下）

**归因环已修的证据（预登记的机制检查，逐集）**：

| 项 | E2' | E2'' | 读法 |
| --- | --- | --- | --- |
| stub c1 紫圆柱未绑定行 | 6 / 6 轮 | **0 / 0** | 颜色唯一的项完全归零——A1 说的 `shape_mismatch` 形态被修掉了 |
| stub c3 未绑定行 | 12 / 12 | **8 / 12** | 剩下的全是 c3 两黄的歧义绑定（v0.4 R3 的拒绝照旧） |
| vlm c1 r0 | 3（结局 BUDGET_EXHAUSTED，0/4） | 3（结局 **blocked，1/4**） | 多完成了一件，终局形态换成了有名字的那一种 |
| vlm c3 r0 / r1 | 13 / 7 | 12 / 11 | 混合；修复不承诺这一格（预登记已写） |

**R1 的账在正式批上结了**：两个 blocked 格的结果对象 `termination_reason` **非空**且
与 `terminated_blocked` 事件的原因一致（驱动 `r1_blocked.all_state_a_reason=True`）——
stub c3 两集写的是 `"holding obj_yellow_1 but no pending goal names it"`，
vlm c1 r0 写的是 `"holding obj_green_1 but no pending goal names it"`。
**E2' 同一批的四个 blocked 集这里全是 None**（残留 #21 的原始形状）。

**验收条目逐条判定**：

| 条 | 判定 | 证据 |
| --- | --- | --- |
| 三格匹配分母 4、无 infrastructure_error | **vlm 格未达成（差 1 集）** | c1 r1 死于 429 配额（`errors.jsonl` 有具名行：5 次尝试全 429）；按 §12 兜底条款交付差值表（见下） |
| 非成功行进账本 | 达成 | `r1_ledger.covered=True`（vlm 的 infra 行带 episode/case/where/error/traceback） |
| manifest 感知通道 + 模型身份 + **接地图 digest 与 E2' 同值** | 达成 | c1 `772f28bf3d6a`、c3 `e889af9ac855`，两批逐位相同（接地图未改，改的是回路怎么用它） |
| RQ13 与 E2' 并排不合并 | 达成 | 上表两列 |
| 归因环已修的机制检查 | **达成** | 未绑定行逐集对照（0/0、12→8、混合项如实记） |
| 两账本合账对上界 | 达成 | 做出 148 / 归属 114 ≤ 165 |
| privileged 冒烟逐轮同形 | 达成 | 11/11/13/13 轮，与 E2' 一致 |

### 花费（Cost 组：真数，USD `null`）

- 探针 **11** + E2'' **148** = **159 次请求**（v0.5 全程），全部免费层；
  `pricing_configured=False` ⇒ `cost_estimate_usd` 保持 `null`（无单价不编数）。
- vlm 格两账本的差 **34 次请求**：`model_calls.jsonl` 记 148，归属到结果的只有 114——
  **c1 r1 那集死于 429，没留下结果，它已经付掉的 34 次请求记在账本里、不记在任何一行结果上**。
  这正是 v0.3 教的两账本口径，本轮第一次在正式批上把差额指到具体一集。

### 预登记规模 × 实达规模（§12 兜底交付）

| 项 | 预登记 | 实达 | 差因 |
| --- | --- | --- | --- |
| 三格 × 4 集 | 12 集 | **11 集产出结局 + 1 集 infrastructure_error** | agnes 免费档配额：c1 r1 的 5 次尝试全 429（具名原因在 `errors.jsonl`） |
| 匹配分母 | 4 / 4 / 4 | 4 / 4 / **3 + 1 死** | 同上 |
| 请求 | ≤165 | 148 | 批在格内跑完，未触发上界；停批规则（连续 3 次 429）未触发 |
| A2 验证批 | 不跑（§11） | 未跑 | 设计交付，跑动留给 v0.6 |

### 一条如实记录的期望偏差（写死过的，仍然发生）

预登记写死过："颜色唯一的项未绑定轮数应当归零；**c3 两黄的歧义绑定与间歇漏检不会被这次修复
带走**，所以三格仍可能读出 0"。实跑完全按这句话发生：**stub c1 的 6→0 兑现，两黄的 12→8 未兑现为 0，
两格仍是 0/4**。另有一处预登记没写到、跑出来的读数：修复让回路**多做了事**（可绑的项变多 → 看的次数变多），
vlm 的 c3 因此从"blocked"变成**撞上每集 32 次的 HTTP 请求预算**（两集 39 请求）。
这是"修掉一个环之后下一个环露头"的实例，记在负结果清单里，不回头改预登记。