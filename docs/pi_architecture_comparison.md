# Pi 与 PPT Director 3.1 定向架构审计

## 1. 审计边界与结论

本审计只比较 Pi 中与 PPT Director 3.1 直接相关的 Agent 事件、资源发现、Session 分支、兼容迁移机制，以及 PPT Director 当前的模式选择、上下文恢复、样张分支、生产门禁和导出链路。没有评估 Pi 的 TUI、多模型 API、聊天体验、插件市场或其他通用能力。

结论：当前 3.1 的总体边界成立，Director 没有接管 PPT Master 的内容理解、视觉设计、布局、资源选择或 SVG 构图。现有单一 `production_state.json`、单一 `events.jsonl` 和 A/B/C 文件分支已经足够，不需要引入 Pi 式 Agent runtime、Session 树或 Extension 系统。

3.1 可以继续实施，但发布前必须修正四个小而关键的缺口：

1. 事件必须按真实可观测时点记录，不能在操作结束后补写虚假的 `started`。
2. capability、mode 和样张输入失效必须使用排除时间戳与展示字段的语义依赖 Hash。
3. `context_rehydrate.md` 必须改为稳定、可重建、无时间戳干扰的确定性结构。
4. 全局输入变化后，template/premium 样张状态必须保留 `three_groups` 结构，不能退化为 standard 样张结构。

此外，premium 当前在 `plan` 前要求 `templates/design_spec.md`，与“Plan 完成后由 PPT Master 生成项目级 `design_spec.md/spec_lock.md`”的既定顺序冲突，应作为同一轮最小修订处理。

## 2. Pi 相关实现证据

| 主题 | Pi 真实实现位置 | 解决的问题 | 对 Director 的含义 |
|---|---|---|---|
| Agent 当前状态 | `packages/agent/src/types.ts:322-346` | 保存当前模型、工具、消息、流式状态、待执行工具和最近错误 | 当前状态只描述“现在是什么”，不等同于历史事件 |
| Agent 生命周期事件 | `packages/agent/src/types.ts:415-430` | 明确定义 agent、turn、message、tool 的开始、更新和结束 | 只有实际拥有调用生命周期时，才有资格记录 started/completed |
| 事件驱动当前状态 | `packages/agent/src/agent.ts:527-573` | 先用事件更新当前状态，再通知监听器 | 事件与当前状态可以分离，PPT Director 不需要把事件历史塞入 Production State |
| 失败语义 | `packages/agent/src/agent.ts:469-509` | 捕获运行失败并产生错误/中止结果，再结束本次运行 | 失败必须有非零结果和可观察的结束事件，不能只写成功式日志 |
| 工具执行包裹 | `packages/agent/src/agent-loop.ts:435-555`、`:668-771` | 调用前发 start，await 工具，异常转错误结果，最后发 end | Pi 能声明工具完成，是因为核心真正等待了工具；外部模型工作流不能照搬该语义 |
| Skill 发现 | `packages/coding-agent/src/core/skills.ts:160-220`、`:277-324` | 通过 `SKILL.md` 发现说明型能力并返回诊断 | Skill 是说明和发现边界，不等于可直接验证的工具能力 |
| Skill 来源与冲突 | `packages/coding-agent/src/core/skills.ts:372-427` | 区分 user/project/path 来源并报告名称冲突 | Director 的 capability snapshot 应保留来源证据，但不需要复制通用资源系统 |
| Extension 运行能力 | `packages/coding-agent/src/core/extensions/loader.ts:217-253` | Extension 可注册工具、命令和事件处理器 | Extension 是可执行扩展；PPT Director 的 Profile/Skill 不应承担这一职责 |
| Extension 资源接入 | `packages/coding-agent/src/core/resource-loader.ts:290-325`、`:338-436` | 外部工作流通过资源加载器接入核心，核心不硬编码业务内容 | 3.1 用内部 Master runtime 和薄调度即可，无需再建 ResourceLoader |
| Session 持久化 | `packages/coding-agent/src/core/session-manager.ts:30-152`、`:946-979` | JSONL 记录带 `id/parentId` 的完整对话树并追加写入 | 这是聊天/Agent 历史，不是 PPT 生产状态的合适模型 |
| Branch/Fork | `packages/coding-agent/src/core/session-manager.ts:1283-1364`、`:1490-1540` | 从任意历史节点继续、提取分支或复制会话 | A/B/C 只有固定两页和三组文件，不需要通用树 |
| Session 兼容迁移 | `packages/coding-agent/src/core/session-manager.ts:226-291` | 旧版本按版本号逐步迁移到新结构 | 3.1 只需读旧 Plan/状态的薄兼容，不应建设通用迁移框架 |
| 测试与发布门禁 | `package.json:16-24`、`:29-38` | 发布前组合静态检查、类型检查、烟测和 workspace 测试 | Director 应补足本次发现的窄测试，不照搬 Pi 的整套发布体系 |

## 3. PPT Director 当前对应实现

| 3.1 对象 | 当前实现 | 当前判断 |
|---|---|---|
| `mode-propose` / `mode-select` | `scripts/director_runtime.py:262-301`、`:378-412`；`scripts/route.py:293-304` | 职责基本正确：Director 推荐/记录模式，并调用 Master 工具；不直接做视觉决策 |
| `capability_snapshot.json` | `scripts/director_runtime.py:196-243` | 四级状态足够；快照 Hash 范围和语义稳定性仍需修正 |
| `generation_mode.json` | `scripts/director_runtime.py:395-407` | 配置与状态分离正确；当前包含 `selected_at`，不应进入语义依赖 Hash |
| `master_handoff.md` | `scripts/director_runtime.py:309-345` | 交接边界清晰；绝对路径和展示文本不应作为下游语义失效依据 |
| `context_rehydrate.md` | `scripts/director_runtime.py:422-459` | 已有单一上下文恢复文件，但含 `refreshed_at` 和绝对路径，字节 Hash 不稳定 |
| Director Plan 3.1 | `integrations/ppt-master/overlay/skills/ppt-master/scripts/director_plan.py:15-30`、`:103-190` | 已禁止 Director 拥有布局、颜色、构图、视觉锚点等字段，边界正确 |
| Strategist 合同 | `integrations/ppt-master/overlay/skills/ppt-master/references/ppt-director-strategist.md:1-53` | 明确 Master 拥有视觉、构图和资源选择；A/B/C 仅固定内容输入，正确 |
| A/B/C 文件分支 | `integrations/ppt-master/overlay/skills/ppt-master/scripts/production.py:205-216`、`:259-284` | 固定三方向、两页、独立 SVG/PNG/Review，足够且比 Session 树更合适 |
| 样张同输入门禁 | `integrations/ppt-master/overlay/skills/ppt-master/scripts/production.py:373-399`、`:509-534` | 已检查同页输入 Hash；Hash 当前包含整个 mode 文件，易受非语义字段影响 |
| `selected_sample.json` | `integrations/ppt-master/overlay/skills/ppt-master/scripts/production.py:585-625` | 是用户选择证据，不是第二状态机；保留合理 |
| `sample-reject` | `integrations/ppt-master/overlay/skills/ppt-master/scripts/production.py:661-688` | 复用同一 Production State，创建下一轮文件分支；无需 Session/fork |
| Production State | `integrations/ppt-master/overlay/skills/ppt-master/scripts/production.py:19-29`、`:183-229` | 单一当前状态和门禁足够，没有必要引入 Pi Session |
| 输入失效 | `integrations/ppt-master/overlay/skills/ppt-master/scripts/production.py:287-334` | 已覆盖全局、SVG、Notes、PNG、Review 和样张批准；grouped 样张结构重置存在缺口 |
| page gate | `integrations/ppt-master/overlay/skills/ppt-master/scripts/production.py:373-422` | 当前页、顺序、样张阶段和方向均有机器门禁，正确 |
| Quality/Render/Review | `integrations/ppt-master/overlay/skills/ppt-master/scripts/production.py:433-460` 及现有 Master 模块 | Router 只调度，检查和渲染由 Master 执行，边界正确 |
| midpoint/deck review | `integrations/ppt-master/overlay/skills/ppt-master/scripts/production.py:691-722` | 当前阶段状态与复核结果分离，满足最低交付门禁 |
| export | `integrations/ppt-master/overlay/skills/ppt-master/scripts/production.py:725-769` | 复用现有 `can_export`、事实门禁和 Master exporter，没有第二导出收据 |
| `events.jsonl` | `scripts/run_log.py:46-100` | 追加写入并与 Production State 分离，方向正确；事件时点需修正 |

## 4. 当前规划已经正确覆盖的内容

以下部分不应继续修改：

1. Director 只保存路由、模式、交接、证据、状态、日志和门禁；PPT Master 保留内容解释、模板分析、视觉方向、资源选择、构图和 SVG 生成权。
2. capability 使用 `available_tool`、`available_model_workflow`、`degraded`、`unavailable` 四级状态。无需置信度、评分或第五种状态。
3. `available_model_workflow` 保留 `verified=false`，只表示调用链具备，不表示本次工作已经完成。
4. `generation_modes.yaml` 是静态配置，`generation_mode.json` 是项目选择，`production_state.json` 是当前运行状态，三者职责已分离。
5. Director Plan 3.1 只描述页面意图、必需信息、来源和事实约束，不提前规定版式与视觉。
6. template/premium 的 A/B/C 使用同一对测试页和相同内容输入，只允许 Master 改变设计方向。
7. `selected_sample.json` 只记录选中的方向和产物 Hash，不承担流程状态。
8. 页面门禁、中途复核、全稿复核和出口门禁继续复用 Master 现有实现。
9. 单一 `events.jsonl` 与单一 Production State 保持分离。
10. 不新增 ResourceLoader、Extension runtime、Session、Review、Exporter 或模板解析器。

## 5. 真实缺口与最小修订

### 5.1 必须调整：事件语义必须忠实于可观测事实

当前 `scripts/route.py:428-433` 在 `dispatch` 完成后，才补写 `capability_preflight_started`、`capability_preflight_finished` 和 `template_analysis_finished`。这会让日志看起来像真实包裹了调用，实际并没有。

最小修订：

- 确定性工具：调用前写 `tool_started`，成功后写 `tool_completed`，异常后写 `tool_failed`；三者使用同一 `operation_id`。
- 外部模型工作流：Director 只能写 `model_workflow_context_issued`；待预期文件真实出现且通过 Hash/结构检查后，写 `model_workflow_artifacts_observed` 或 `model_workflow_gate_failed`。
- 如果宿主没有提供外部 Agent 的开始/结束回调，不得写 `model_workflow_started/completed`。
- `events.jsonl` 继续追加写；Production State 只记录当前是否可继续，不复制事件历史。

这借鉴的是 Pi 的“只有核心真正 await 的工具才能产生真实 start/end”，不是复制 Pi 的 Agent loop。

### 5.2 必须调整：增加稳定的语义依赖 Hash

当前问题：

- capability 快照包含 `captured_at`、绝对 `runtime_root` 和展示性错误文本。
- mode 记录包含 `selected_at`、估算时间/Token和推荐说明。
- grouped sample 的 `input_hash` 直接包含整个 `generation_mode.json` 文件 Hash（`production.py:392-399`）。
- runtime fingerprint 只覆盖手工列出的若干文件（`director_runtime.py:75-86`），没有覆盖实际工作流引用闭包。

最小语义对象固定为：

```text
capability_semantic_hash = hash(
  schema_version,
  master_commit/runtime_version,
  generation_modes配置Hash,
  capability_id,
  execution_type,
  入口文件的项目内相对路径与内容Hash,
  引用闭包的相对路径与内容Hash,
  工具依赖状态,
  Python主次版本与关键依赖版本
)

mode_semantic_hash = hash(
  mode,
  quality_preference,
  fidelity_requirement,
  replication_mode,
  sample_strategy,
  source内容Hash集合,
  template内容Hash,
  capability_semantic_hash
)

sample_input_hash = hash(
  mode_semantic_hash,
  template内容Hash,
  Director Plan中该页的规范化内容字段
)
```

必须排除：

- `captured_at`、`selected_at`、`selection_time`。
- 运行耗时、Token估算、展示名称、推荐理由和说明文字。
- 可由逻辑路径和内容 Hash 替代的绝对路径。
- `context_rehydrate.md` 的生成时间和排版差异。

无需新增文件或通用依赖图。只在现有 `director_runtime.py` 中对当前 capability 配置和已解析引用做排序、规范化与 Hash。

### 5.3 必须调整：`context_rehydrate.md` 使用确定性结构

继续保留现有一个文件，不新增 JSON 状态。建议固定为：

```text
schema_version
command
mode
page_id
semantic_dependency_hash
required_context[]:
  role
  logical_path（项目相对路径或runtime逻辑路径）
  sha256
current_page（Director Plan原始字段，键顺序固定）
previous_artifacts[]:
  page_id
  svg_hash
  png_hash
  review_hash
sample_feedback_hash（存在时）
```

排序规则固定为 `role + logical_path`。删除 `refreshed_at`；绝对路径可在 CLI 返回值中用于打开文件，但不得进入语义 Hash。该文件只是可重建上下文视图，不是状态源，不需要历史版本。

### 5.4 必须调整：全局失效后保留 grouped 样张结构

`production.py:295-304` 在任一全局 Hash 变化后，把 `samples` 重置为 standard 结构：

```text
{page_ids, status, approved_hashes}
```

这会丢失 template/premium 的 `strategy=three_groups`、`directions` 和 round 信息。下一次样张流程可能失去 A/B/C 门禁。

最小修订：失效时调用现有 `_sample_state(project, page_ids)`，而不是手写通用字典；同时补一个“template/premium 全局输入变化后仍保持 three_groups”的测试。不要增加新状态。

### 5.5 必须调整：premium 的 Plan 与 Design Spec 顺序

当前 `scripts/route.py:297-304` 要求 premium 在 `plan` 前已有 `templates/design_spec.md`，而既定链路是：模板处理完成后先生成 Director Plan，再由 PPT Master 生成项目级 `design_spec.md/spec_lock.md`。

最小修订：

- `mode-select` 只执行可确定验证的 Master intake/import/vector 工具，并返回需要读取的现有 Master workflow。
- 模型工作流若尚未执行，只记录 `context_issued`，不得标记模板分析完成。
- `plan` 不以 `templates/design_spec.md` 为前置条件。
- 项目级 `design_spec.md/spec_lock.md` 仍由 Master 在 Plan 后生成并由现有 `lock-spec` 冻结。

这不是让 Director 接管设计，而是纠正执行顺序和事件真实性。

## 6. 建议调整但不阻断 3.1 的项目

1. capability workflow 的职责检查目前主要依赖关键词（`director_runtime.py:148-193`）。3.1 可保留，但测试应覆盖“文件存在但只有标题/占位文本”以及“引用文件变化会刷新快照”。不需要语义模型或评分器。
2. capability snapshot 可记录 `checks` 和 `reason_code`，但不要扩展状态枚举。
3. 对 managed 项目的兼容只做读取旧 Plan/状态所需的薄标准化。Pi 的多版本 Session migration 可作为以后出现真实迁移需求时的参考，不属于 3.1 必需项。
4. 日志可增加 `operation_id`、`expected_outputs` 和 `observed_outputs`；不要记录客户正文、模型思维过程或完整 Review 文本。
5. 测试补充事件顺序、语义 Hash 稳定性、grouped 失效和 premium 顺序即可，不需要引入 Pi 的 workspace 测试框架。

## 7. 明确不采用

| 不采用项 | 原因 |
|---|---|
| Pi Session JSONL 树 | A/B/C 是有界文件候选，不需要对话重放、任意分叉或 leaf 导航 |
| branch/fork/branch summary | 会把样张选择扩张成通用会话系统，并产生第二套状态语义 |
| Extension runtime | PPT Master 已是内部runtime；再建 Extension 会重复能力发现和执行边界 |
| ResourceLoader/插件发现 | 3.1 使用固定内置 Master 能力，不需要动态插件市场和资源优先级 |
| TUI、多模型 API、聊天历史 | 与 PPT 生产最低门禁无关 |
| 第二套 Review 或 Export receipt | 现有 `.review/*.json`、Production State 和 `can-export` 已覆盖 |
| capability 评分或置信度 | 四级状态加检查证据已经足够，评分会制造伪精度 |
| Director 自建模板分析或视觉规划 | 直接侵犯 PPT Master 职责边界 |
| 记录不可观测的 Agent started/completed | 日志会把“发出说明”误写为“模型真实执行” |

## 8. 十个重点问题的直接回答

1. **当前 Director 是否越界参与设计？** 总体没有。Director Plan 3.1 已禁止布局、色彩、构图和视觉字段。唯一边界风险是 premium 在 Plan 前要求模板 `design_spec`，应纠正顺序，但这不是当前已经实现了一套视觉设计器。
2. **四级 capability 状态是否足够？** 足够。工具与模型工作流通过 `execution_type` 区分，模型工作流保留 `verified=false`。不增加置信度和评分。
3. **context_rehydrate 应使用什么结构？** 使用一个稳定、可重建的 Markdown 视图：固定 schema、命令、模式、页码、逻辑路径与 Hash、当前页原始 Plan 字段、上一页产物 Hash和反馈 Hash；固定排序，不含时间戳。
4. **外部 Agent 无法直接观测时记录什么？** 只记录上下文已发出、期望产物、输入语义 Hash；后续记录产物已观察并通过门禁，或门禁失败。不要声称模型已开始或完成。
5. **semantic dependency hash 如何排除噪声？** 对业务字段、内容 Hash、相对逻辑路径和依赖版本做规范化排序；排除时间戳、耗时、估算、展示文本、推荐理由和绝对路径。
6. **A/B/C 是否需要完整 Session 树？** 不需要。现有固定目录、两页相同输入、三组产物 Hash、`selected_sample.json` 和 Production State 足够。
7. **Production State 是否足够？** 足够。它已表达当前阶段、样张、页面、复核和导出门禁。引入 Session 会产生第二套当前状态和迁移负担。
8. **哪些 3.1 部分不应再改？** Director/Master 边界、四级能力状态、一个 Plan、一个状态、一个事件日志、同页 A/B/C、现有 Review/page gate/export、Master 自由构图。
9. **哪些建议推迟到 3.1 后？** 通用迁移框架、动态 Extension、跨项目 Session、能力插件化、复杂运行图、模型执行遥测。只有真实兼容或宿主观测需求出现后再做。
10. **是否存在过度借鉴 Pi 的风险？** 很高。Pi 的 Session、Extension 和 ResourceLoader 解决的是通用编码 Agent 问题，直接引入会把 Director 从最小工作流外壳变成第二个 Agent 平台。

## 9. 受影响文件

### 必须调整

- `scripts/director_runtime.py`
  - 语义依赖 Hash。
  - 确定性 `context_rehydrate.md`。
  - premium 模板处理只调度 Master，不提前拥有项目 design spec。
- `scripts/route.py`
  - 真实事件时点。
  - 移除 premium 的 Plan 前 `templates/design_spec.md` 条件。
- `scripts/run_log.py`
  - 支持同一 `operation_id` 的真实 started/completed/failed 或 context-issued/artifacts-observed 事件，不增加第二日志。
- `integrations/ppt-master/overlay/skills/ppt-master/scripts/production.py`
  - grouped 样张失效时复用 `_sample_state`。
  - grouped sample 使用 `mode_semantic_hash`，不使用整个模式文件字节 Hash。
- `tests/test_director31.py`
  - 增加上述四类窄回归。

### 无需调整

- `integrations/ppt-master/overlay/skills/ppt-master/scripts/director_plan.py` 的 3.1 非视觉字段边界。
- PPT Master 模板解析器、Quality Checker、Visual Review、SVG renderer 和 exporter。
- Production State 顶层枚举与 Review/Export 状态机。
- `runtime/config/generation_modes.yaml` 的三模式与四级能力状态；如实现语义 Hash，只读取现有配置内容。

## 10. 是否需要修改当前 3.1 规划

需要做**局部修订**，不需要重新规划：

- 在 capability 章节增加语义依赖 Hash 的规范化边界。
- 在日志章节区分“确定性工具生命周期”和“不可观测模型工作流证据”。
- 在 context rehydrate 章节删除时间戳参与语义依赖，固定确定性结构。
- 在失效章节明确 grouped 样张必须保留 A/B/C 结构。
- 在 premium 顺序章节明确 Plan 先于项目级 `design_spec/spec_lock`。

除此之外，3.1 当前架构可以继续实施。完成这些小修订并补齐对应测试后，应停止扩张，进入真实 template/premium 项目回归。
