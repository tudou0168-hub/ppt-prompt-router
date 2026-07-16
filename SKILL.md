---
name: ppt-prompt-router
description: PPT Director 单 Skill 入口。完成场景路由、内容导演、风险样张、逐页复核和受控导出。
version: 3.1.0
---

# PPT Director 3.1

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
  `director_profile.md`并执行首次能力预检；不得规划内容、分析模板或生成设计规范。
- `mode-propose`：读取能力快照；快照缺失或runtime、依赖变化时先自动重做预检，
  再推荐 `standard`、`template` 或 `premium`。`degraded`不得自动推荐，
  `unavailable`不得选择。
- `mode-select`：由用户明确选择模式，写入唯一模式记录和Master handoff，再调用
  PPT Master现有工具或工作流处理模板。premium默认使用fidelity；mirror仅在用户
  明确要求且完整工作流可用时开放。
- `plan`：完整读取命令返回的 `MASTER.md`、Strategist说明、Profile和源材料，
  只生成 `analysis/director_plan.json`。模式未选择前不得规划。
- `lock-spec`：Director Plan存在后，完成并冻结 `design_spec.md`与`spec_lock.md`。
- `page-begin`：逐项读取命令返回的当前页Director字段、设计系统和Executor说明，
  再判断内容关系、资源或自定义SVG。
- `page-check`：调用Master现有机器检查和渲染。
- `page-review`：必须真实打开最新PNG，按Master现有Visual Review规则独立复核。
- `page-pass`：仅放行与当前SVG、PNG、Review Hash一致的页面。
- `sample-confirm`：standard沿用三张风险样张A/B/C；template/premium在三组同页
  样张完成后，由用户在后续独立调用中选择A、B或C方向，不得由模型自行批准。
- `sample-reject`：用户拒绝template/premium三组方向后返回样张生产，下一轮必须
  读取用户反馈；不创建新状态或平行计划。
- `review`：仅允许 `midpoint` 或 `deck`。
- `export`：仅在现有 `can-export` 与全部门禁通过后调用Master导出。

## 导演边界

Router决定受众、目的、语体、叙事节点、事实边界和关键退化风险；不替
PPT Master选择具体布局、资源或构图。Director Plan是唯一内容规划源，
每页只表达一个核心观点，并保留页面意图、必需信息、来源和事实约束。

standard的三张样张必须分别验证：

1. 信息密度与卡片堆砌风险。
2. 复杂流程、机制或关系风险。
3. 图片、图表、架构或项目独特视觉能力。

封面、目录、结语和普通文字页不得作为样张。样张通过即停止在
`sample_confirmation`，等待用户后续A/B/C。

template与premium在Plan完成后固定同一对测试页：一个封面或总览页、一个
关系复杂正文页。A/B/C三组的page_id、page_intent、required_messages、
source_refs、factual_constraints、参考模板和内容范围必须完全相同；只有
PPT Master的设计方向、视觉表达、构图和信息组织可以不同。Director不得规定
三组版式差异，也不得用简单标题页、纯文字页或单一卡片页充当复杂页。

## 最低交付边界

- 每页SVG通过Master现有Quality Checker。
- 每页渲染后真实查看PNG并绑定Review。
- 当前页通过后才能进入下一页。
- SVG、Notes、Plan或设计锁变化时旧检查自动失效。
- 中途复核通过后回到`production`，全稿复核通过后进入`export_ready`。
- 无来源的数字、年份、日期、金额、比例、机构、责任部门和案例成效阻断导出。
- `government_strategy`与`decision_meeting`正文最低20px，其他Profile最低18px；
  辅助正文16px，脚注与来源12px。
