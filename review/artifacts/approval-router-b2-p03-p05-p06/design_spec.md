<!-- ppt-master-schema: design-spec/v1 -->
# 审批服务局2026年上半年工作总结及下半年工作谋划（B2验证页） - Design Spec

## I. Project Information

| Item | Value |
| --- | --- |
| Project Name | 审批服务局2026年上半年工作总结及下半年工作谋划（B2验证页） |
| Canvas Format | PPT 16:9（1280 × 720） |
| Page Count | 3（仅 P03、P05、P06） |
| Primary Language | zh-CN |
| Target Audience | 管委会、党工委领导及分管政务服务的决策层，需快速掌握阶段成效、服务机制与下半年抓手。 |
| Communication Intent | 以可核验成效汇报上半年工作，并把机制成效与下半年重点衔接，支持领导统筹理解政务服务的进度和方向。 |
| Desired Audience Outcome | 领导能够辨识业务办理、基层民生服务与下半年六项重点之间的逻辑，并将数字赋能、服务下沉等任务理解为持续提质增效的能力路径。 |
| Core Message / Ask / Action | 上半年服务供给在业务增长中实现提质增效；下半年应以六项重点把阶段改革沉淀为常态服务能力。 |
| Delivery Context | 主场景为领导汇报中的投屏讲解；可作为会后阅读和统筹参考。 |
| Artifact Afterlife | 汇报留档与后续工作统筹参考。 |
| Reading Mode | balanced |
| Content Strategy | 平衡重构：只生产原专业页面导演稿指定的 P03、P05、P06；保留原始材料事实、统计时点和“计划/探索”边界。 |
| Design Style | 结论先行的政务数据简报：浅色出版纸面、严谨栅格、深蓝主色与少量政务红强调。 |
| Formula Policy | text-only |
| AI Image Acquisition Path | not applicable |
| Generation Mode | continuous |
| Spec Refinement | disabled |
| Speaker Notes | enabled — delegated final Stage-2 proactive policy |
| Custom Animations | disabled — delegated final Stage-2 proactive policy |
| Narration Audio | disabled — delegated final Stage-2 proactive policy |
| Created Date | 2026-08-10 |

## II. Canvas Specification

| Property | Value |
| --- | --- |
| Format | PPT 16:9 |
| Dimensions | 1280 × 720 |
| viewBox | `0 0 1280 720` |
| Margins | 48px 外边距；页眉、页脚各保留 28px 运行空间 |
| Content Area | x=48–1232，y=96–650 |

## III. Visual Theme

### Theme Style

- **Mode**: pyramid
- **Visual style**: data-journalism
- **Theme**: 政务数据编辑部——以细分栏、统计标签、数据刻度和克制的引导线组织领导汇报；不做装饰性插画。
- **Tone**: 稳健、清晰、可核验、面向决策。

### Color Scheme

| Role | HEX | Purpose |
| --- | --- | --- |
| Background | #F6F3ED | 温暖纸面底色，降低高密度数据阅读疲劳 |
| Secondary background | #E8EEF3 | 数据带、浅层区块与结构分区 |
| Primary | #173F63 | 标题、主数字、核心结构与政务可信感 |
| Accent | #B52B32 | 关键增长、重点抓手与结论强调 |
| Secondary accent | #2E7D79 | 线上协同、服务改善与正向结构区分 |
| Body text | #18242E | 正文、标签与注释 |
| Surface | #FFFFFF | 内容承载面，保持主数据可读性 |
| Grid | #C7D1D9 | 发丝分隔线、刻度与辅助结构 |

## IV. Typography System

### Font Plan

| Role | Character (Reference) | Primary | English if non-English | Fallback tail |
| --- | --- | --- | --- | --- |
| Title | 理性、权威的衬线标题 | Songti SC | Georgia | serif |
| Body | 清晰、紧凑的政务信息阅读 | Microsoft YaHei | Arial | sans-serif |
| Data | 等宽、便于核验数字 | Menlo | Menlo | monospace |

- **Title stack**: Songti SC, STSong, SimSun, serif
- **Body stack**: Microsoft YaHei, PingFang SC, Arial, sans-serif
- **Data stack**: Menlo, Consolas, monospace
- **Role rationale**: Data 使用等宽字体，保证数字、百分比与统计口径的对齐和快速核验。

### Font Size Hierarchy

| Purpose | Anchor Size (px) |
| --- | ---: |
| Body | 24 |
| Title | 44 |
| Subtitle | 30 |
| Annotation | 18 |
| Data | 22 |
| Footnote | 16 |

## V. Layout Principles

### Page Structure

- **Header area**: 左侧页码/栏目与结论式标题；右侧保留“审批服务局｜2026 H1 / H2”运行标识。
- **Content area**: 使用 12 列编辑栅格；P03 以主数字和证据带为骨架，P05 以闭环与场景双栏组织，P06 以六项并列战场的能力矩阵承载。
- **Footer area**: 统一统计口径/来源行与页码，保持页面的可核验性。

### Spacing Specification

| Element | Current Project |
| --- | --- |
| Safe margin | 48px |
| Content block gap | 20px |
| Icon-text gap | 10px |

## VI. Icon Usage Specification

- **Primary bundled library**: tabler-outline
- **Stroke Width**: 2

| Icon Path | Suitable Scenarios |
| --- | --- |
| tabler-outline/chart-bar | 数据成效、业务量与统计口径 |
| tabler-outline/clipboard-list | 台账、闭环管理与任务清单 |
| tabler-outline/building-community | 基层服务、社区与服务场景 |
| tabler-outline/briefcase-2 | 企业服务、招商包保 |
| tabler-outline/cpu | 数字赋能、智能体和数据共享 |
| tabler-outline/map-pin | 服务下沉、便民服务圈与触点 |

## VIII. Image Resource List

| Filename | Dimensions | Ratio | Purpose | Type | Layout pattern | Crop Policy | Acquire Via | Status | Reference | text_policy | page_role |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

## IX. Content Outline

### Part 1: 上半年服务质效与民生机制

#### Slide 03 - 审批与大厅服务实现“办件增长、效率提升、线上协同”

- **Audience move**: 从“大厅业务量大”转向“在业务增长中，线上协同与企业服务已形成可核验的质效结构”。
- **Layout**: 编辑部式三段结构：左侧超大总办件数与同比增长；中部以“线上协同”占比环与业务量带支撑；右侧以企业业务占比和补充口径构成窄侧栏。下方统一标注上半年统计口径。
- **Title**: 审批与大厅服务实现“办件增长、效率提升、线上协同”
- **Core message**: 上半年累计办理 43.41 万件、日均 3529 件，同比增长 12.9%；线上办理和企业业务共同支撑服务供给提质增效。
- **Content**: 主数据“434,069 件”“日均 3,529 件”“同比 +12.9%”；线上办件“228,367 件｜52.6%｜同比提高 0.7 个百分点”；企业主体业务“276,924 件｜63.8%”；补充核验“市场主体 118,456 户，较去年净增 6,822 户”“纳税人 85,720 户，较去年增长 10,835 户”。
- **Visualization**: 数据驱动的主数字、占比环和横向业务量带；比例和刻度均直接依据原始材料数值。
- **Native-ready**: no
- **Native shape suggestion**: 统计口径侧栏可采用圆角矩形与基础线条组合，形成可编辑的“数据条目—数值—注释”结构。

#### Slide 05 - 以闭环协同和场景延伸，把政务服务做进基层与群众身边

- **Audience move**: 从“便民服务是分散项目”转向“闭环管理、跨部门场景和有诉即办共同把服务能力延伸到基层和群众身边”。
- **Layout**: 左侧用一表通的三段闭环与覆盖范围构成机制主轴；右侧上下排列“政务+工会”服务量与“有诉即办”群众诉求解决量；中间以细线连接但不误画为单一流程。
- **Title**: 以闭环协同和场景延伸，把政务服务做进基层与群众身边
- **Core message**: “一表通”以全链条闭环压减重复报送，并与跨部门服务场景和有诉即办机制共同增强基层减负与群众可感体验。
- **Content**: 机制链“任务部署—督办整改—成效复盘”；覆盖“20 个区直部门、6 个办事处、101 个村（社区）”“配置 411 个账号”“精简区级报表至 112 项”；体验支撑“政务+工会服务群众 2 万余人次”“上半年解决群众各类诉求 197 件”；已开展场景标签“政务+健康”“政务+婚检”。
- **Visualization**: 数据驱动的闭环带、覆盖范围数据块与两枚服务成效拉引数字；仅“一表通”呈现明确闭环，其他场景保持并列。
- **Native shape suggestion**: 闭环采用三个圆角节点与基础连接线；不使用箭头把并列服务场景串成虚构流程。

### Part 2: 下半年能力升级路径

#### Slide 06 - 下半年以六项重点推进，把阶段改革转化为常态服务能力

- **Audience move**: 从“下半年任务很多”转向“六项重点是围绕同一能力目标展开的并列战场，每项都有可执行的关键抓手”。
- **Layout**: 顶部以“常态服务能力”为唯一目标锚点；下方两行三列形成六项重点阵列，使用统一编号、短标题和一条关键抓手。底部以克制的收束语连接高新区高质量发展，不补造目标数字或时间表。
- **Title**: 下半年以六项重点推进，把阶段改革转化为常态服务能力
- **Core message**: 以攻坚任务和民生实事为底线，招商包保、审批改革、专区增值、数字赋能和服务下沉六项工作并列推进，持续提质增效。
- **Content**: 01 攻坚任务与民生实事：网络计划书、挂图作战；02 招商包保：推动项目落地，实施“收集—办理—反馈—销号”全链条管理；03 审批改革：承接新事项、巩固已上线事项；04 专区增值：资源联动与服务下沉；05 数字赋能：继续完善“高小·i”研发建设，推进免证办和一表通；06 服务下沉：15 分钟便民服务圈、惠企服务、有诉即办与微创新。
- **Native shape suggestion**: 六项重点可采用基础圆角矩形和编号圆形组成的并列任务模块；仅在“总体目标—六项重点”关系中使用细连接线，不暗示实施先后顺序。

## X. Speaker Notes Requirements

- **Generation**: enabled
- **Filename**: match each SVG filename under `notes/`
- **Content**: 使用正式、简洁的领导汇报口吻；解释统计时点和计划边界，不引入材料外事实。P03 说明全部统计为上半年；P05 说明一表通的试点与并列场景关系；P06 强调“高小·i”为继续研发建设、免证办覆盖扩大为方向性目标。
- **Total duration**: 约 3 分钟（每页约 1 分钟）
- **Notes style**: formal
- **Presentation purpose**: report and align
