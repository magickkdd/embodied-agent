# 连续决策具身智能体 · v0.8 阶段日志

> 立项：2026-10-13 · 规格：`Continuous-Decision-Embodied-Agent-SPEC-v0.8.md`
> 主攻方向：**握持孤儿归因 + 相机新血**（D1'''''，用户选定）
> 纪律沿用 v0.7 §2：预登记先于跑动；判据进测试与仪器；每条读数带论域；
> 负结果保留并给原因；`cost_estimate_usd` 保持 `None`；批间轮换、批内单席；感知/决策两本账。

---

## P0 预检（2026-10-13，零成本，当众跑；分区之后）

v0.8 的立项与单仓分区在同一个窗口内完成（`54d7c4e` SPEC、`6be4422` 分区、`5262209` §2.7 落账），
所以本阶段的第一次预检跑在**新布局**上：

| 检查 | 读数 | 与 SPEC §2.7 的预测 |
| --- | --- | --- |
| `schema_fingerprint()` 逐项相等 | **MATCH** | 一致 |
| `cli freeze --check` | rc=0，`frozen list matches: 2f1c74f52e91` | **不变** ✓ |
| `cli prereg --check` | rc=0，`72271eadb43d…` | **由 `23abe58f…` 变到 `72271ea…`** ✓（不变量 I5 的文件路径主张随迁移更新） |
| `cli em-pairs --check` | rc=0，`em set matches: 7df449ed2f4d` | **不变** ✓ |
| 长视野表 `agent_lab.evaluation.long_horizon_tasks --check` | `lh frozen OK b9fce17fbbf6` | **v2 表哈希不变** ✓ |
| 工作树 | 干净（3 个提交未推） | — |

**四条门里有三条的账与 SPEC 写的一致，唯一变化的是 prereg 印记**——这正是 §2.7 说的那一条
（不变量 I5 的主张是文件路径，迁移必然改它）。表哈希不变，因为本阶段不改表。

**对仪器的影响（已记进 SPEC §2.7，执行时确认）**：
`work/v07/` 的仪器在 HEAD 上导入已断（`embodied_agent.evaluation.*` → `agent_lab.evaluation.*`），
复现以各自版本的提交为准；**v0.8 的仪器一律落 `work/v08/`，副本内的导入改写为 `agent_lab` 新路径**，
不回写 `work/v07/`。

---

## P1 判据（握持孤儿归因，判据先行，跑后未改一字）

### 语料（只读，五个集）

| 代 | 集 | 终态理由 |
| --- | --- | --- |
| v0.6 E2'''（v1 表） | `c1 r0` | `holding obj_green_1 but no pending goal names it`（36 请求） |
| v0.6 E2'''（v1 表） | `c1 r1` | 同上（34 请求） |
| v0.7 E2''''（v2 表） | `c1 r0` | 同上（42 请求） |
| v0.7 E2''''（v2 表） | `c1 r1` | 同上（32 请求） |
| v0.7 E2''''（v2 表） | `c3 r1` | `holding obj_purple_2 but no pending goal names it`（15 请求） |

### RQ21 的三候选判据（SPEC §3）

| 候选 | 定义 | 判据（可机械判的才算判据） |
| --- | --- | --- |
| **(a) 簿记缺陷** | 抓取时 pending 目标里有该物，抓取后 pending 无该物，且**外部无原因** | 该物在抓取轮的 pending 集里**在**；在下一轮**不在**；且两轮之间**没有**任何"该目标已完成 / 被绑定到别的实体 / 被取消"的事件 |
| **(b) 语义真孤儿** | 抓取时 pending 里**从来就没有**该物 | 该物在**每一个**有 pending 快照的轮次里都不在 pending 集（决策者拿了无目标物 ⇒ 决策侧现象） |
| **(c) 时序错位** | pending 的消解与握持状态并发更新、顺序错位 | 同一轮内存在两条相互矛盾的记录（一条说 pending 已消解该目标、另一条说该目标仍 pending），或握持状态在该目标消解**之后**才写入 |

### 逐集必交付的时间线（SPEC §5）

每一集给：抓取轮与被握对象 · 每一轮的 pending 目标集快照 · pending 变更事件（哪个目标在何时、
因什么被移除）· 终态。**判据先行，仪器后写；仪器只填表，不做判断以外的发挥。**

### privileged 对照（判据的第三项）

孤儿**从不**出现在 privileged 格（v0.4–v0.7 每代 privileged 都是 4/4 成功）。
若归因指向相机特有的信息面（例如绑定漂移由感知更新触发），必须写明这条依赖。

### 修复的门槛

只有 **(a) 坐实**才进入 P2 的修复裁定（D2'''''）。(b) 与 (c) 都是合法判定，
(b) 直接转决策线读数如实记，(c) 指向并发顺序，需另立契约。

---

## P1 握持孤儿归因（2026-10-13，零花费，判据先行，跑后未改一字）

仪器：`work/v08/r21_attribution.py`（归因表 + 三候选判定）、
`r21_timeline.py`（逐轮时间线的阅读面）；产物 `work/v08/r21_orphan_attribution.json`。

### 代码路径（判定的锚点）

| 位置 | 代码 | 作用 |
| --- | --- | --- |
| `embodied_agent/core/planner.py:165` | `return _control(ctx, "blocked", f"holding {held} but no pending goal names it")` | 阻塞判据：`pending` 里没有任何一条的 entity_id 等于握持物 |
| `embodied_agent/core/planner.py:119-126` | `if item.value != true and world.has_entity(item.entity_id): pending.append(...)` | **pending 只保留 entity_id 是真实实体的行** |

第二条是关键：**一条按属性对指名的行（`"{'shape': 'cube', 'color': 'green'}"`）的 `entity_id`
是字面属性串，`world.has_entity(属性串)` 为假，于是这条行被 pending 直接丢弃**——
一个"未绑定但仍待办"的目标就此从簿记里消失，握持检查随后只能判阻塞。

### 五个集的时间线读数（逐集）

| 集 | 握持物 | 请求 | 轮数 | 漂移轮（行由 id 变属性） | 抓取轮按 id 指名 | 抓取后按 id 指名 | 每个漂移轮的帧都缺声明颜色 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| v06 E2''' c1 r0 | obj_green_1 | 36 | 7 | 4,5,6,7 | **是** | 是 → **否** | 是 |
| v06 E2''' c1 r1 | obj_green_1 | 34 | 6 | 3,6 | **是** | 是 → **否** | 是 |
| v07 E2'''' c1 r0 | obj_green_1 | 42 | 9 | 3,5,6,8,9 | **是** | 是 → **否** | 是 |
| v07 E2'''' c1 r1 | obj_green_1 | 32 | 7 | 4,5,6,7 | **是** | 是 → **否** | 是 |
| v07 E2'''' c3 r1 | obj_purple_2 | 15 | 4 | 1,2,3,4 | **是** | 是 → **否** | **否**（见下） |

**五个集的形态完全一致**：抓取那一轮 pending **确实**按 id 指名了握持物，
**下一轮就不指名的了**——因为那一帧里 `bind_attributes` 解不出声明，行退回属性串，被
`world.has_entity` 丢掉。

### 三候选判定

| 候选 | 判定 | 依据 |
| --- | --- | --- |
| (b) 语义真孤儿 | **否** | 五个集在抓取轮都按 id 指名过握持物（"从来就没有"不成立） |
| (c) 时序错位 | **否** | 没有任何一轮同时存在两条互相矛盾的记录；握持与 pending 在不同轮更新，没有并发可错 |
| **(a) 簿记缺陷** | **是（但"无外部原因"这一款不成立）** | pending 丢行 + 握持检查只比 id，这条路径确实把"未绑定但待办"变成死路；**但漂移本身有外部原因**：四个 c1 集的漂移轮，帧都缺声明颜色（#26） |

### c3 r1 是另一种漂移（#25 而不是 #26）

c3 r1 的第 1–3 轮里，`yellow/cube` 行一直按属性指名，而**帧确实带着 yellow**——
因为 c3 有两件黄（`obj_yellow_1` cube / `obj_yellow_6` cuboid），
读侧只报一件（**同名共现 0/760**，v0.7 M1），`yellow/cube` 这个对从未同时出现 ⇒ 绑定失败（#25）。
第 4 轮帧丢了 purple 与 red，`purple/cube` 与 `red/cuboid` 也随之漂移（这才是 #26）。

它的触发链还多一步：`pick obj_purple_2`（completed）→ `place obj_purple_2`（**uncertain**）
→ `pick obj_purple_2`（completed）→ 下一轮该行已漂移 ⇒ 阻塞。

### 归因结论（一句话）

**握持孤儿 = 绑定漂移（由 #26 间歇漏检或 #25 两黄歧义触发）+ 一条真实的簿记缺陷**：
`pending_assignments` 把"未绑定但仍待办"的行丢掉，握持检查又只按 id 匹配，
于是漂移变成死路而不是一次降级。**privileged 格从不出孤儿**，
因为特权态下属性总能解出，行一直是 id 指名——这条依赖因此**指向信息面，不是决策逻辑**。

### 修复设计草案（交 D2'''''，未实施）

| 项 | 内容 |
| --- | --- |
| 落点 | `embodied_agent/core/planner.py` 的 `pending_assignments` 与 `decide` 的握持检查（**决策侧/簿记**，原则 20 管不着；与 v0.5 修目标侧绑定同类） |
| 改法 1 | pending **不再丢弃**按属性指名的待办行：把 `world.has_entity(item.entity_id)` 放宽为"id 是实体 **或** 该行声明了属性"，并在 pending 里带上属性 |
| 改法 2 | 握持检查在 id 不匹配时，按**声明属性**与 pending 行匹配（与读侧同一套属性语义） |
| 期望效果 | 孤儿类**消失**（不再 blocked），但**不保证成功**：漂移的外部原因（#26/#25）仍在，能不能放对要看新血批的读数 |
| 不做 | 不动读侧（原则 20）；不回填五个历史集（SPEC §2.3） |
| 风险 | 行为漂移（契约先红后绿 + 回归只增不减 + 并排不合并）；可能把死路换成"放错托盘"的新失败形态 |

---

## P2 修复落地（D2'''''：修，2026-10-13）

### 契约先红后绿（`tests/contract/test_v08_orphan_pending.py`，5 条）

| 测试 | 修前 | 修后 |
| --- | --- | --- |
| 未绑定待办行在决策口**留在 pending** | **RED**（行被丢弃） | GREEN |
| 握持检查**按属性**匹配该行 ⇒ place 而非 blocked | **RED**（`holding obj_green_1 but no pending goal names it`） | GREEN |
| 握持物谁都不指名时**仍然 blocked**，理由串不变 | GREEN | GREEN |
| id 指名路径不动（无行为漂移） | GREEN | GREEN |
| plan 路径**不**把属性串变成 `pick(object_id="{...}")` 步骤 | GREEN | GREEN |

三条控制测试在修前就绿——它们是"不许动的地方"的钉子，只有前两条是红的。

### 实现（`embodied_agent/core/planner.py`，决策侧/簿记）

| 改动 | 内容 |
| --- | --- |
| `_declared_attributes(entity_id)` | 读回未绑定行字面属性串里的属性对；解析失败就当它是 id（绝大多数情况） |
| `pending_assignments(..., include_unbound=False)` | **决策口** opt-in：属性键名的待办行不再被 `world.has_entity(属性串)` 丢掉；**plan 口默认仍只收可解出的行**（模式 A 零漂移） |
| `_target_for_held(held, goal, world)` | 先按 id 匹配，再按**声明属性**与握持物自身的属性匹配（读侧与验证器同一套属性语义） |
| `decide()` 的握持分支 | 改用上面这个匹配；匹配不到仍然返回原来那句 blocked |

**没有动**：读侧（原则 20）、冻结记录类（`core/v02.py` 一行未改——所以 fingerprint 逐项相等）、
五个历史集（SPEC §2.3：不回填）。

### 门与回归

`schema_fingerprint: MATCH` · `freeze rc=0 (2f1c74f52e91)` · `prereg rc=0 (72271eadb43d…)` ·
`em-pairs rc=0 (7df449ed2f4d)` · 长视野表 `lh frozen OK b9fce17fbbf6`（**表哈希不变**）·
契约层 **914 passed / 6 skipped** · 全量回归 **1311 passed / 27 skipped**
（分区后基线 1306，**只增不减**：+5 条新契约）。

**行为漂移的风险按 SPEC §3 的纪律**由新血批承担：修复后的行与五历史集**并排不合并**，
第五类在新批里出不出现是 RQ23 的对照点。

---

## P3 新血批预登记（2026-10-13，早于第一次请求）

`configs/experiment/v08_newblood_preregistration.json` 落盘，四格写死：

### 格一：case 集与规模（D3'''''）

**c2 / c4 / c5 × {privileged, stub, vlm} × 2 repeats = 9 格 / 18 集**，
每格匹配分母 **2**（一个 case 一格，所以一格的读数不会被邻居稀释）。
c6 不进（known-hard，#24，D 级未裁）。

### 格二：上界推导（D4'''''，原则 19）

| 项 | 数 | 依据 |
| --- | --- | --- |
| 单集末次请求的**保守**取值 | **56** | c1 36–42、c3 54–56 的实测峰值取大者 |
| 花钱的集 | 6（只有 vlm 格，3 case × 2 repeat） | privileged/stub 各 0 请求 |
| goal-parse | 6（每 (case, repeat) 一次） | 与前几代同口径 |
| 小计 | 6×56 + 6 = **342** | |
| **上界** | **342 × 1.25 = 427 请求** | SPEC §6 估域 420–500 ✔ |

**写明一句**：c2/c4/c5 没有需求画像，这个 56 是**先例不是测量**；它们 4–5 个物体、
低于 c3 的 6 个，需求"大概更低"——但"大概"不是数，把上界定在已知峰值以下才是那种
会让批提前停住的乐观。相机格单集上界**仍 48/48**（本批只动簿记这一个变量）。

### 格三：判据（三条新的，全部机械可判）

| 判据 | 怎么判 |
| --- | --- |
| **集级与行级分开** | 每个失败集写两行：集级终态理由（`termination_reason`/`failure_type`）与行级未绑定行形态（v0.7 文档门抓出的混淆，升格为判据） |
| **RQ22 推广检验** | 每个 stub/vlm 格算 `nonzero = successes ≥ 1`；任一非零 ⇒ "相机不行"被推翻且该 case 成为非零样板；全零 ⇒ 从 2 case 实测推广到 **5 case 实测** |
| **RQ23 对照点** | 逐格报 `holding X but no pending goal names it` 的集数，与五个历史集并排；历史集**不回填** |
| 需求画像 | c2/c4/c5 的每集请求/两账/未绑定行入账，补上 v0.7 表里的 `no_confirmed_evidence` 空白 |

### 格四：预期分级与停止规则

- **0 合法且有价值**：全零就是"'相机通道不行'从 2 case 变成 5 case 的实测"；
- 修复的**窄**效果预写：第五类应当**不再出现**（集继续跑而不是被阻塞），
  但"死路消失"**不等于**"格子非零"——漂移的外部原因（#26 / #25）本阶段没动；
- 诚实对照项：若握持物现在按属性匹配被放好、集继续跑、后来撞墙，
  那是**两条读数**（死路没了 + 需求是真的），记成"修好了"是粉饰，拒绝；
- 3×429 停批、格级断点、已跑格不重跑、3×`REPEATED_INVALID` 风险预写；上界触顶即停。

### 批前门（当众跑，第一次请求之前）

`schema_fingerprint: MATCH` · `freeze rc=0 (2f1c74f52e91)` · `prereg rc=0 (72271eadb43d…)` ·
`em-pairs rc=0 (7df449ed2f4d)` · 长视野表 `lh frozen OK b9fce17fbbf6`（**表哈希不变**）。