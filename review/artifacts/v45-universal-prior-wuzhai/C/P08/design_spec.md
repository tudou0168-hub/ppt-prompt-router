<!-- ppt-master-schema: design-spec/v1 -->
# 五寨县“人工智能+”规划方案 P08 - Design Spec

## I. Project Information

| Item | Value |
| --- | --- |
| Project Name | 五寨县“人工智能+”规划方案 P08 决策沟通样页 |
| Canvas Format | PPT 16:9 (1280 × 720) |
| Page Count | 1 |
| Primary Language | zh-CN |
| Target Audience | 五寨县相关领导 |
| Communication Intent | 为规划方案决策沟通说明直接面向办事过程的拟建能力、共同实施依赖与优先验证方向。 |
| Desired Audience Outcome | 领导能够理解七项拟建能力不是并列采购清单，而是围绕高频事项形成“少填、少等、少跑、少重复”闭环，并将事项标准、材料规则、身份核验、系统对接和合规条件作为推进前置核验项。 |
| Core Message / Ask / Action | 先以高频且规则相对清晰的事项验证闭环，再把智能填单、预审、政策匹配、云端协同和服务留痕扩展为可协同的办事能力体系。 |
| Delivery Context | 领导汇报场景；单页需支持演示中的快速读图与会后复核。 |
| Artifact Afterlife | 作为15页规划汇报中 P08 的样页证据，用于审阅和后续制作对照。 |
| Reading Mode | balanced |
| Content Strategy | balanced default；以冻结页面方向为专业表达约束，只使用原始规划材料中的拟建能力与待核实条件。 |
| Design Style | 决策优先、关系可读、证据层级明确的专业科技汇报样页。 |
| Formula Policy | text-only |
| AI Image Acquisition Path | not applicable |
| Generation Mode | continuous |
| Spec Refinement | disabled |
| Speaker Notes | disabled — final Stage-2 proactive policy for this P08-only sentinel. |
| Custom Animations | disabled — final Stage-2 proactive policy. |
| Narration Audio | disabled — final Stage-2 proactive policy. |
| Created Date | 2026-08-10 |

- **Template Application**: 采用已安装的 Universal Professional Visual Prior Style 的关系、证据与阅读顺序方法；页面仍为自由组合的扁平样页，不继承品牌、版式原型或页面清单。

## II. Canvas Specification

| Property | Value |
| --- | --- |
| Format | PPT 16:9 |
| Dimensions | 1280 × 720 |
| viewBox | `0 0 1280 720` |
| Margins | 40px outer safe margin |
| Content Area | 1200 × 640 within the safe margin |

## III. Visual Theme

### Theme Style

- **Mode**: pyramid
- **Visual style**: dark-tech
- **Theme**: 深色决策界面；以一条由办事场景流向可验证闭环的发光轨迹组织阅读，重点能力以局部高亮而非同权卡片表达。
- **Tone**: 克制、清晰、可追溯；“拟建能力”“共同依赖”“待核实”保持语义区分。

### Color Scheme

| Role | HEX | Purpose |
| --- | --- | --- |
| Background | #07131F | 深色底场，承载负空间与流程轨迹 |
| Secondary background | #102438 | 能力模块与依赖带的低对比底面 |
| Primary | #4DE1FF | 关键路径、主结论与高亮能力 |
| Accent | #9CFF64 | 可优先验证的闭环提示 |
| Secondary accent | #FFC857 | 待核实依赖与注意提示 |
| Body text | #EAF4FA | 正文和标签的高对比阅读 |

## IV. Typography System

### Font Plan

| Role | Character (Reference) | Primary | English if non-English | Fallback tail |
| --- | --- | --- | --- | --- |
| Title | 强断言、干净无衬线 | Microsoft YaHei | Arial | Arial |
| Body | 高可读、紧凑无衬线 | Microsoft YaHei | Arial | Arial |
| Annotation | 细小等宽标签 | Microsoft YaHei | Consolas | Arial |

- **Title stack**: Microsoft YaHei, Arial
- **Body stack**: Microsoft YaHei, Arial
- **Annotation stack**: Microsoft YaHei, Consolas, Arial
- **Role rationale**: Annotation uses a monospace companion to distinguish dependency and scope labels from decision copy.

### Font Size Hierarchy

| Purpose | Anchor Size (px) |
| --- | ---: |
| Body | 19 |
| Title | 34 |
| Subtitle | 18 |
| Annotation | 13 |

## V. Layout Principles

### Page Structure

- **Header area**: 左上断言式标题与一行限制条件，右上以 `P08 / 智能办事` 作为低权重定位标签。
- **Content area**: 以一条横向“办事场景 → 智能能力 → 直接减摩擦”的主路径承载四个能力簇；下方独立依赖带连接全部能力簇。
- **Footer area**: 左侧标注“拟建能力”；右侧说明结果与规模须先以本地基线和试点评估核验，避免把材料中的预期当作已实现成效。

### Spacing Specification

| Element | Current Project |
| --- | --- |
| Safe margin | 40px |
| Content block gap | 20px |
| Icon-text gap | 8px |

## VI. Icon Usage Specification

- **Primary bundled library**: none

| Icon Path | Suitable Scenarios |
| --- | --- |

## VIII. Image Resource List

| Filename | Dimensions | Ratio | Purpose | Type | Layout pattern | Crop Policy | Acquire Via | Status | Reference | text_policy | page_role |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

## IX. Content Outline

### Part 1: 智能办事能力闭环

#### Slide 08 - 智能办事应先在高频、规则清晰的事项中验证“少填、少等、少跑、少重复”闭环

- **Audience move**: 从把七项建设内容理解为并列功能清单，转为按办事场景、能力组合与共同依赖审视其可验证的实施闭环。
- **Layout**: 标题下方先给出“先验证闭环”的结论；中部以四段横向服务路径显示场景到能力的对应关系，左起为“填报与材料”“企业服务与咨询”“基层远程办”“窗口与勘验”。每段由深色承载面、青色路径节点与一条结果短语构成，权重依次由标题、路径、模块内支持信息递减。底部用一条连续的黄色依赖带跨接四段，并以细连接线说明所有能力共用的前置条件；避免把四段做成同权装饰卡片。
- **Title**: 智能办事应先在高频、规则清晰的事项中验证“少填、少等、少跑、少重复”闭环
- **Core message**: 智能填单、预审、政策匹配、云端协同与服务留痕只有嵌入统一事项流程和共同依赖，才会从单点功能转化为可落地的服务改造。
- **Content**:
  - **主路径引导语**：以高频、规则相对清晰的事项先形成可验证闭环。
  - **填报与材料**：`自然语言引导 → 材料识别 → 表单预填 → 合规校验`；对应 AI 智能填单与 AI 智能预审，减少填报摩擦和窗口重复核对。
  - **企业服务与咨询**：`企业画像 ↔ 政策条件匹配`，并提供对话式办事指引；对应惠企政策匹配智能体与智能云客服。
  - **基层远程办**：`远程视频 + 身份核验 + 材料上传 + 电子签名 → 云端办理`；对应虚拟云综窗，支撑服务向基层延伸。
  - **窗口与勘验**：`录音质检 / 过程归档` 与 `远程踏勘 / 全程留痕`；对应窗口数字工牌与智能云勘验，支撑可追溯服务质量管理。
  - **共同依赖（跨模块）**：事项标准、材料规则、身份核验、业务系统对接、合法合规条件。
  - **页脚核验提示**：原材料中的“支持30个高频事项”“填表平均时长由15分钟缩短至3分钟”等为建设预期；须先核实五寨县高频事项、材料字段、系统权限、可用接口和合规条件。
- **Visualization**: 定性“场景—能力—结果”主路径；四个场景簇按办理过程从左至右阅读，依赖带从下方跨接全部场景簇，强调“能力共用前置条件”而非线性项目清单。
- **Native shape suggestion**: 以圆角矩形为能力承载面、直线连接符为场景到能力的流向；共同依赖带采用分段圆角矩形和向上细连接线，保留原生业务图形可编辑性。

## X. Speaker Notes Requirements

- **Generation**: disabled
