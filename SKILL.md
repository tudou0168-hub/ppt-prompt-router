---
name: ppt-prompt-router
description: PPT Director 单 Skill 入口。完成场景路由、内容导演、风险样张、逐页复核和受控导出。
version: 4.0.0
---

# PPT Director 4.0 Phase 1

本 Skill 是唯一公开入口。内部 `runtime/ppt-master/` 保留 PPT Master 的
Strategist、设计资源、SVG、检查、复核和导出能力，但不注册为第二个 Skill。

客户材料、日志、SVG、PNG、Review 和 PPTX 只能写入 Skill 目录外的项目。

## 唯一命令入口

```bash
python3 <skill>/scripts/route.py <command> ...
```

公开命令仅有：

```text
start
context
submit
approve
mode-propose
mode-select
plan
lock-spec
page-begin
page-check
page-review
page-pass
sample-confirm
sample-reject
review
status
export
```

不得直接执行内部 Master CLI、直接写 `svg_output/`、跳过 Visual Review，
或直接调用导出脚本。受控步骤失败时不得切换 legacy 流程。

## 阶段读取

- `start`：只创建项目、分离导入内容材料与参考PPT、记录Hash、编译唯一
  `director_profile.md`并执行首次能力预检；不生成 Plan 或设计产物。
- `mode-propose`：读取能力快照；快照缺失或runtime、依赖变化时先自动重做预检，
  再推荐 `standard`、`template` 或 `premium`。`degraded`不得自动推荐，
  `unavailable`不得选择。
- `mode-select`：由用户明确选择模式，写入唯一模式记录和Master handoff，再调用
  PPT Master现有工具或工作流处理模板。premium默认使用fidelity；mirror仅在用户
  明确要求且完整工作流可用时开放。
- `context`：为指定角色生成覆盖式最小 Context；角色只能读取其合同规定的输入。
- `submit`：按固定角色—产物映射接收 Plan、Template Profile、Genome、当前 SVG 或 Review。
- `approve`：唯一批准入口。`brief` 只接受 A，`design` 接受 A/B/C，`page` 只接受 A 并绑定
  当前 SVG、PNG 和 Review Hash；普通 CLI 只记录 `cli_unverified`。
- `plan`：兼容入口；新 Phase 1 流程应由 Content Strategist 经 `submit` 提交
  `analysis/director_plan.json`。
- `lock-spec`：机械校验 `design_genome.json` 并确定性编译 `design_spec.md` 与
  `spec_lock.md`；不得手写或篡改编译产物。
- `page-begin`：逐项读取命令返回的当前页Director字段、设计系统和Executor说明，
  再判断内容关系、资源或自定义SVG。
- `page-check`：调用Master现有机器检查和渲染。
- `page-review`：必须真实打开最新PNG，按Master现有Visual Review规则独立复核。
- `page-pass`：三张设计探针也走正式页面门禁并封存；探针全部通过后停止等待 Design Approval。
- `sample-confirm`：兼容别名，内部映射到 `approve --type design`。
- `review`：仅允许 `midpoint` 或 `deck`。
- `export`：仅在现有 `can-export` 与全部门禁通过后调用Master导出。

## 导演边界

Router决定受众、目的、语体、叙事节点、事实边界和关键退化风险；不替
PPT Master选择具体布局、资源或构图。Director Plan是唯一内容规划源，
每页只表达一个核心观点，并保留页面意图、必需信息、来源和事实约束。

三张设计探针必须分别验证：

1. 信息密度与卡片堆砌风险。
2. 复杂流程、机制或关系风险。
3. 图片、图表、架构或项目独特视觉能力。

封面、目录、结语和普通文字页不得作为探针。三个探针通过即停止在
`sample_confirmation`，等待真实用户 Design Approval。

所有模式在 brief approval 后由 Template Analyst（需要模板时）和 Visual Director 形成
Template Profile 与 Design Genome；不生成 style sample、A/B/C 方向或 two-by-three
方向页。Genome 只表达全局视觉方向与逐页视觉任务，不规定坐标、栏数、卡片数、固定组件、
图形类型或图片位置。Director只选择页面，不指定关系类型、视觉锚点、图片策略、布局、
颜色、字体或构图。

## 最低交付边界

- 每页SVG通过Master现有Quality Checker。
- 每页渲染后真实查看PNG并绑定Review。
- 当前页通过后才能进入下一页。
- deep fusion 正式页完成质检后必须等待用户 page approval，确认后才能seal。
- `brief` 与 `design` 等待节点统一返回 `AWAITING_USER_CONFIRMATION`、
  `confirmation_kind` 和 `next_command`，随后结束执行。
- SVG、Notes、Plan或设计锁变化时旧检查自动失效。
- 中途复核通过后回到`production`，全稿复核通过后进入`export_ready`。
- 无来源的数字、年份、日期、金额、比例、机构、责任部门和案例成效阻断导出。
- `government_strategy`与`decision_meeting`正文最低20px，其他Profile最低18px；
  辅助正文16px，脚注与来源12px。
