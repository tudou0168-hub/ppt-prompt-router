<!-- ppt-master-schema: design-spec/v1 -->
# 五寨县“人工智能+”规划方案 — P13 - Design Spec

## I. Project Information

| Item | Value |
| --- | --- |
| Project Name | 五寨县“人工智能+”规划方案 — P13 推进路径 |
| Canvas Format | PPT 16:9 (1280 × 720) |
| Page Count | 1 |
| Primary Language | zh-CN |
| Target Audience | 五寨县相关领导，关注建设边界、推进风险、跨部门协同与扩展决策 |
| Communication Intent | 为 15 页规划方案中的 P13 提供决策沟通：先说明不应在基线未核实前直接铺开建设，再对齐“摸底—试点—评估—扩展”的可控推进机制，并支持后续授权与协同。 |
| Desired Audience Outcome | 领导清楚四阶段不是既定工期或预算承诺，认同以可核验条件和试点结果决定是否、如何分步扩展。 |
| Core Message / Ask / Action | 扩展不是既定下一步；应先核实底数并完成可控试点，以本地评估结论和运维条件作为分步扩展依据。 |
| Delivery Context | 以汇报人主讲的规划决策沟通为主，并支持会后审阅。 |
| Artifact Afterlife | 作为后续推进讨论、条件核验与决策留痕的单页依据。 |
| Reading Mode | balanced |
| Content Strategy | balanced default；保留原始材料的建设方向与场景依据，对冻结方案中的推进路径作决策导向重组，不把外地案例或预期成效转写为五寨县已验证事实。 |
| Design Style | 决策优先的金字塔论证 + Swiss-minimal；以单一时序主轴、阶段闸门和反馈回路建立清晰的阅读顺序。 |
| Formula Policy | text-only |
| AI Image Acquisition Path | not applicable |
| Generation Mode | continuous |
| Spec Refinement | disabled |
| Speaker Notes | disabled — final Stage-2 proactive policy for this P13-only execution slice |
| Custom Animations | disabled — final Stage-2 proactive policy |
| Narration Audio | disabled — final Stage-2 proactive policy |
| Created Date | 2026-08-10 |

- **Template Application**: 应用已安装的 Universal Professional Visual Prior 实验性 Style 方法：让核心结论、时序关系、阶段闸门和不确定性在同一阅读路径中分层呈现；不继承品牌、版式原型或页面顺序，页面自由扁平构成。

## II. Canvas Specification

| Property | Value |
| --- | --- |
| Format | PPT 16:9 |
| Dimensions | 1280 × 720 |
| viewBox | `0 0 1280 720` |
| Margins | 40 px 外边距；顶部为标题区，底部保留决策注记区 |
| Content Area | 1200 × 640，主路径在中部横向展开 |

## III. Visual Theme

### Theme Style

- **Mode**: pyramid
- **Visual style**: swiss-minimal
- **Theme**: 克制、可信的政务决策沟通；以深蓝建立秩序，以蓝色强调可进入下一阶段的条件，以浅灰显示尚待核实或待决策的信息。
- **Tone**: 审慎、清晰、行动导向，不渲染技术炫酷感。

### Color Scheme

| Role | HEX | Purpose |
| --- | --- | --- |
| Background | #F7F9FC | 干净的近白底场，承载大留白 |
| Secondary background | #EAF0F8 | 阶段说明与注记的轻层级底色 |
| Primary | #0B3A6E | 标题、主时序轴与核心结论 |
| Accent | #1E78C8 | 阶段闸门、已满足条件与反馈路径焦点 |
| Secondary accent | #88AEDD | 次级连接、分区与辅助标注 |
| Body text | #152536 | 正文与条件说明 |

## IV. Typography System

### Font Plan

| Role | Character (Reference) | Primary | English if non-English | Fallback tail |
| --- | --- | --- | --- | --- |
| Title | Neo-grotesque, bold, conclusion-first | PingFang SC | Aptos | Microsoft YaHei, sans-serif |
| Body | Neo-grotesque, regular, precise | PingFang SC | Aptos | Microsoft YaHei, sans-serif |

- **Title stack**: PingFang SC, Microsoft YaHei, sans-serif
- **Body stack**: PingFang SC, Microsoft YaHei, sans-serif

### Font Size Hierarchy

| Purpose | Anchor Size (px) |
| --- | ---: |
| Body | 24 |
| Title | 42 |
| Subtitle | 32 |
| Annotation | 18 |

## V. Layout Principles

### Page Structure

- **Header area**: 左对齐的结论式标题，副标题只承担“不要预设工期、预算和批次”的边界提示。
- **Content area**: 一条从左到右的阶段主轴承载四个不等权步骤；每个阶段把目标与关键工作绑定，阶段之间用可见闸门而非普通箭头表示进入条件；评估环节用一条回返线反馈到试点。
- **Footer area**: 以细规则和一条审慎注记说明本页为建议性推进方法，不将任何时间、预算、批次或责任分工写成已确认事实。

### Spacing Specification

| Element | Current Project |
| --- | --- |
| Safe margin | 40 px |
| Content block gap | 24 px |
| Icon-text gap | 12 px；本页默认不使用图标 |

## VI. Icon Usage Specification

- **Primary bundled library**: none

| Icon Path | Suitable Scenarios |
| --- | --- |

## VIII. Image Resource List

| Filename | Dimensions | Ratio | Purpose | Type | Layout pattern | Crop Policy | Acquire Via | Status | Reference | text_policy | page_role |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

## IX. Content Outline

### Part 4: 可控推进与扩展决策

#### Slide 13 - 推进路径：以“摸底—试点—评估—扩展”控制建设节奏

- **Audience move**: 从“可按建设清单直接铺开”的预期，转为“扩展须由底数、试点结果和运维条件共同触发”的决策判断。
- **Layout**: 以一条左到右的主路径组织四个阶段，第一、二、三阶段之间分别嵌入小型“Gate”竖向闸门；四个阶段的视觉权重随决策成熟度递进，但不使用等权卡片墙。阶段三下方回返至阶段二的细线，明确“评估发现问题→回到试点优化”的反馈闭环。右端扩展区保持留白，突出“以成熟度决定范围”而非预设规模。
- **Title**: 扩展不是既定下一步：应以摸底、试点和评估结果控制节奏
- **Core message**: 在基线未核实前，应先完成小范围验证；只有阶段闸门通过，才进入下一阶段并形成分步扩展方案。
- **Content**:
  - 顶部副标题：建议性推进方法｜具体起止时间、投资、建设批次和责任安排待后续决策制定。
  - 阶段 01｜摸底与定标：核实现状、事项与数据底账；明确建设边界与优先级。Gate 01：事项、数据、现场条件和规则可核验。
  - 阶段 02｜场景试点：选择高频、规则清晰、数据条件较好的场景；验证服务闭环。Gate 02：在真实条件下可运行，问题与风险可闭环。
  - 阶段 03｜评估与固化：复盘体验、效率、质量、合规与运维；形成标准流程。Gate 03：本地实测结论与持续运维条件足以支撑扩展判断。
  - 阶段 04｜分步扩展：按成熟度扩展至更多事项、窗口和基层网点；同步统筹底座能力。右端结论：扩展范围由评估结论决定。
  - 反馈注记：评估发现问题时，返回试点优化，而不是直接扩大范围。
  - 页脚注记：本页不预设日期、预算、采购方式、批次或责任单位；原始材料未提供这些已确认信息。
- **Visualization**: 定性时序与依赖关系；主阅读路径为“摸底→试点→评估→扩展”，闸门标识进入条件，细回返线仅表达“评估→试点优化”的反馈关系。

## X. Speaker Notes Requirements

- **Generation**: disabled
