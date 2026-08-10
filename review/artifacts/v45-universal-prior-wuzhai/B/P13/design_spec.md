<!-- ppt-master-schema: design-spec/v1 -->
# 五寨县“人工智能+”政务服务规划方案（P13执行切片） - Design Spec

## I. Project Information

| Item | Value |
| --- | --- |
| Project Name | 五寨县“人工智能+”政务服务规划方案（P13执行切片） |
| Canvas Format | PPT 16:9 (1280 × 720) |
| Page Count | 1 |
| Primary Language | zh-CN |
| Target Audience | 五寨县相关领导 |
| Communication Intent | 为规划方案决策沟通说明实施推进原则、阶段闸门与反馈机制，支持审慎确定后续推进方式。 |
| Desired Audience Outcome | 领导理解建设应以核实结果和试点实测为依据，并认可“先摸底、可控试点、评估固化、成熟扩展”的推进节奏。 |
| Core Message / Ask / Action | 在基线未核实前，不承诺日期、预算或建设批次；以阶段闸门决定是否进入下一步。 |
| Delivery Context | 领导汇报场景，PPT为主、口头说明为辅。 |
| Artifact Afterlife | 作为规划决策沟通材料留存，并为后续实施方案提供路径边界。 |
| Reading Mode | balanced |
| Content Strategy | balanced default；冻结版页纲作为专业表达方向，原始规划材料为事实权威。 |
| Design Style | 专业、审慎、决策导向的瑞士极简信息图。 |
| Formula Policy | text-only |
| AI Image Acquisition Path | not applicable |
| Generation Mode | continuous |
| Spec Refinement | disabled |
| Speaker Notes | disabled — workflow default |
| Custom Animations | disabled — workflow default |
| Narration Audio | disabled — workflow default |
| Created Date | 2026-08-10 |

## II. Canvas Specification

| Property | Value |
| --- | --- |
| Format | PPT 16:9 |
| Dimensions | 1280 × 720 |
| viewBox | `0 0 1280 720` |
| Margins | 48px outer safe margin |
| Content Area | x=48–1232, y=42–666 |

## III. Visual Theme

### Theme Style

- **Mode**: pyramid
- **Visual style**: swiss-minimal
- **Theme**: 深蓝决策底板上的四段推进轨道；阶段编号、阶段动作与闸门条件构成一条可回看的实施路径。
- **Tone**: 审慎、清晰、可控、面向行动。

### Color Scheme

| Role | HEX | Purpose |
| --- | --- | --- |
| Background | #F7F9FC | 主信息底板与留白 |
| Secondary background | #E9EEF5 | 阶段信息卡与辅助区域 |
| Primary | #0B1F3A | 标题、主轨道与决策锚点 |
| Accent | #146CFF | 当前推进方向、关键箭头与阶段编号 |
| Secondary accent | #00A58A | 阶段闸门通过与“可进入下一步”提示 |
| Body text | #1C2B3A | 正文与说明文字 |

## IV. Typography System

### Font Plan

| Role | Character (Reference) | Primary | English if non-English | Fallback tail |
| --- | --- | --- | --- | --- |
| Title | 黑体、强结论 | Microsoft YaHei | Arial | sans-serif |
| Body | 黑体、清晰扫描 | Microsoft YaHei | Arial | sans-serif |

- **Title stack**: Microsoft YaHei, Arial, sans-serif
- **Body stack**: Microsoft YaHei, Arial, sans-serif

### Font Size Hierarchy

| Purpose | Anchor Size (px) |
| --- | ---: |
| Body | 18 |
| Title | 42 |
| Subtitle | 22 |
| Annotation | 14 |

## V. Layout Principles

### Page Structure

- **Header area**: 左上结论式标题与一行边界说明；右上仅保留页码标识。
- **Content area**: 中部由一条方向性主轨串联四个阶段卡；每卡包含阶段目标、关键工作和进入条件。
- **Footer area**: 左侧显示“阶段闸门决定是否进入下一步”，不呈现日期、预算或批次。

### Spacing Specification

| Element | Current Project |
| --- | --- |
| Safe margin | 48px |
| Content block gap | 24px |
| Icon-text gap | 0px |

## VI. Icon Usage Specification

- **Primary bundled library**: none

| Icon Path | Suitable Scenarios |
| --- | --- |

## VIII. Image Resource List

| Filename | Dimensions | Ratio | Purpose | Type | Layout pattern | Crop Policy | Acquire Via | Status | Reference | text_policy | page_role |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

## IX. Content Outline

### Part 1: 实施推进路径

#### Slide 13 - 以阶段闸门控制节奏：摸底、试点、评估、扩展

- **Audience move**: 从“按功能清单直接铺开建设”转向“以核实与验证结果决定下一步范围”。
- **Layout**: 采用左至右四段推进轨道。每个阶段为一张严格对齐的浅色信息卡，上方有序号与阶段名称，中部列关键工作，下方有绿色闸门条；“评估与固化”通过一条回流箭头指向“场景试点”，显示不达标时先优化再扩大。右侧以深蓝窄栏强调“无日期、无预算、无既定批次”。
- **Title**: 以阶段闸门控制节奏：先试点验证，再分步扩展
- **Core message**: 在基线未核实前，应完成底数与规则确认，选择可控场景验证服务闭环，经评估后再形成扩展方案。
- **Content**:
  - 01 摸底与定标：核实现状、事项与数据底账；明确建设边界和优先级。闸门：事项、数据、接口与现场条件形成可核验清单。
  - 02 场景试点：选择高频、规则清晰、数据条件较好的场景；验证从服务触达、受理到反馈的闭环。闸门：试点方案明确人工兜底、责任接口与运行条件。
  - 03 评估与固化：复盘群众体验、窗口效率、服务质量、合规与运维；形成可复用的标准流程。闸门：以本地实测结果确认成效、风险和可持续运营条件。
  - 04 分步扩展：按成熟度扩展至更多事项、窗口和基层网点；统筹底座能力。闸门：经决策确认后确定扩展范围、节奏和保障安排。
  - 边界说明：四步为建议性实施方法，不代表原始材料已确定工期；具体起止时间、投资和建设批次待决策后制定。
- **Visualization**: 非数据型四阶段时序与反馈关系；绿色闸门表示“满足条件后进入下一阶段”，蓝色回流箭头表示“评估发现问题则返回试点优化”。
- **Native shape suggestion**: 四张基础矩形阶段卡、圆形阶段编号、直线连接器与一条回流弧形连接器；均以原生基本形状优先。

## X. Speaker Notes Requirements

- **Generation**: disabled
