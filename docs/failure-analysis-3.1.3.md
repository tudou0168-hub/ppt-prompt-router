# PPT Prompt Router 3.1.3：B1 失败样本故障分析

## 范围与方法

本分析只针对审批服务局 Router B1 的 8 页完整样本，不调整 Router 的 routing、scoring、Profile 或回归数量。

逐页读取了原始 DOCX、B1 的 `analysis/presentation_plan.md`、`design_spec.md`、`spec_lock.md`、SVG 和 Speaker Notes；并实际查看了 B1 的 SVG 预览、PPTX 实际渲染 PNG 和 Contact Sheet。原始 Stage 1 Communication Contract 与 Director handoff 未保存在 B1 项目中，计划顶部仅保留 Router/Profile/Stage 1 哈希，因此不能把这一段称为完整可审计证据。

### 视觉证据

- B1 SVG Contact Sheet：`/Users/muzi/Documents/ppt-master/skills/ppt-master/projects/router-regression-20260809/approval-router-b-r1_ppt169_20260809/validation/contact_sheet_svg_rendered.png`
- B1 PPTX 实际渲染 Contact Sheet：`/Users/muzi/Documents/ppt-master/skills/ppt-master/projects/router-regression-20260809/approval-router-b-r1_ppt169_20260809/validation/contact_sheet_rendered.png`
- A 原生 SVG Contact Sheet：`/Users/muzi/Documents/ppt-master/skills/ppt-master/projects/router-regression-20260809/approval-native-a-r1_ppt169_20260810/validation/contact_sheet_svg_rendered.png`
- A 原生 PPTX 实际渲染 Contact Sheet：`/Users/muzi/Documents/ppt-master/skills/ppt-master/projects/router-regression-20260809/approval-native-a-r1_ppt169_20260810/validation/contact_sheet_rendered.png`

PPTX 实际渲染均由同一 LibreOffice 环境完成。两套 PPTX 都出现中文缺字方框，原因是该渲染环境没有 `Microsoft YaHei`，因此它证明了交付环境的字体风险，不能用来区分 A/B 的中文视觉质量。A/B 的中文视觉比较以下列 SVG 实际渲染 PNG 为准，同时保留 PPTX 渲染 PNG 作为独立问题证据。

## B1 逐页追踪

| 页面 | 原始沟通任务 | Director 实际输出 | Design Spec 实际翻译 | 最终视觉结果 | 首次发生质量退化的阶段 | 责任判断 |
| --- | --- | --- | --- | --- | --- | --- |
| P01 | 用正式开场建立“改革提效、服务增温”的总判断 | “三束上行光汇聚为服务效能”；庄重留白 | 深蓝留白封面，三束细光汇聚主标题 | 只剩标题、两条线和日期，三束光/服务效能的视觉动作没有成立；正式但无记忆点 | PPT Master Executor | PPT Master Executor |
| P02 | 用运行数据证明服务效能提升 | 43.4万主角，后接线上、企业、主体等证据带 | 左主数字、右纵向证据列 | 主数字和证据列均被保留，未退化为卡片；但证据仍是无语境的清单，无法看出“服务质效为何提升” | Director / Router handoff | Director / Router handoff |
| P03 | 说明牵头任务的进度与质量 | 80%主结论，四条关键证据支撑 | 80%主结论由四条指标支撑 | 仪表盘和三行文字可读，但“任务—抓手—服务结果”的关系没有可视化，80%只是装饰性仪表 | Director / Router handoff | Director / Router handoff |
| P04 | 解释改革怎样减少群众等待 | 压减动作 + 两组前后时限比较 | 四项压减 + 两组前后时限对比 | 这是 B1 最接近可用的一页：规模、压减和对比被保留；但仍是两组文字与色条，缺少办事场景/流程证据 | 多因素 | 多因素 |
| P05 | 解释企业专区如何组织全周期服务 | 中心企业需求 + 周边协同能力系统 | 中心需求与周边能力形成系统关系 | 关系图被忠实执行，但外围是抽象标签，没有服务旅程、部门角色、入口/出口或真实案例；“系统”不可感知 | Director / Router handoff | Director / Router handoff |
| P06 | 把下半年六项任务讲成路径而非清单 | 六条工作线连续推进至全年目标 | 单一路径串联六条工作线 | 六个节点只是名称挂在波浪线上，未表达优先级、依赖、阶段、产出或责任；路径图只是“反卡片”的形式 | Director / Router handoff | Director / Router handoff |
| P07 | 将人员和运维诉求转为领导应判断的保障事项 | 两项基础保障托住前端服务与改革任务 | 两条基础保障托住服务与改革结果 | 两个框和一条线仍然是抽象标签；没有风险、后果、决策动作或保障缺口的证据，支撑诉求力度弱 | Director / Router handoff | 多因素 |
| P08 | 以全年目标收束 | 服务能力汇聚为发展支撑 | 结语留白，服务能力向发展支撑汇聚 | 极简结尾本身合理，但与 P01 视觉几乎同构，不能形成有意设计的首尾呼应 | PPT Master Executor | PPT Master Executor |

## 语义链诊断

### 已经真实传递的部分

`presentation_plan.md → design_spec.md → SVG` 的关系类型大体被消费：P02 的主数字加证据列、P04 的前后对比、P05 的中心系统、P06 的连续路径、P07 的双支撑都能在最终页面中找到对应物。因而问题不是“Stage 2 完全无视 Plan”或“Executor 把所有页重新做成同一组卡片”。

### 首次失真的位置

大多数失败首先发生在 Director handoff / Director 页面计划：六字段能说清页面在讲什么，却没有清楚说明页面要让人先看见什么、什么必须退后、哪一项事实充当视觉证据、关系的可感知方式是什么，以及这页与前后页怎样形成体验差异。

例如，P06 的 `visual_semantics: 六条工作线向同一全年目标连续推进` 是正确的语义标签，却不是视觉导演：它没有给出年度目标、工作线、阶段/依赖、关键产出之间谁是视觉主角，也没有规定数据或事实如何让这条路径可信。Executor 因此只能合理地把它实现成“六点一线”。P05 和 P07 的问题相同。

`hierarchy` 在 B1 中常写作“主角=…；支撑=…”，但没有明确视觉层（hero、证据、解释、背景）与证据对象；`rhythm_intent` 只标记 anchor/dense/breathing；`Evidence / image material` 对多数页是“不使用外部图片”或“数字来自原始材料”。这些字段齐全，却不足以成为页面级视觉导演。

### Stage 2 与 Executor 的责任边界

- Stage 2 基本把 B1 计划翻译成了对应的 Layout 描述，未发现大面积回退到通用卡片模板。
- Executor 对 P01 的“三束光”、P08 的首尾差异没有充分实现；其余核心问题并非执行漏掉了明确构图，而是执行了过于抽象的构图。
- 全册持续使用深蓝底、同一标题栏、金线、白字、线条与圆点，说明 Executor 缺少能在相同政务身份下形成视觉场景变化的输入和素材，也没有自行补足该变化。

## A / B1 真实视觉比较

### A 的运行条件

A 使用同一原始 DOCX、PPT Master 4.4、8 页范围、ppt169、蓝金政务视觉、无外部图片、同一备注/导出要求。唯一意图上的差异是 A 不使用 Router。指定的 `government-report` 工作区在当前 PPT Master 4.4 模板校验中为旧格式并失败；B1 项目也没有安装后的 `templates/` 产物。因此两者都不能声称真正消费了该工作区，A 以相同的蓝金视觉约束走当前可执行的 free-design 原生流程。这是本次比较的前置条件失效，不应归因于 Router。

### 关键页并排 PNG

- P02：`/Users/muzi/Documents/ppt-master/skills/ppt-master/projects/router-regression-20260809/approval-native-a-r1_ppt169_20260810/validation/ab_comparison_svg/ab_02_service_evidence.png`
- P04：`/Users/muzi/Documents/ppt-master/skills/ppt-master/projects/router-regression-20260809/approval-native-a-r1_ppt169_20260810/validation/ab_comparison_svg/ab_04_reform_experience.png`
- P05：`/Users/muzi/Documents/ppt-master/skills/ppt-master/projects/router-regression-20260809/approval-native-a-r1_ppt169_20260810/validation/ab_comparison_svg/ab_05_enterprise_service.png`
- P06：`/Users/muzi/Documents/ppt-master/skills/ppt-master/projects/router-regression-20260809/approval-native-a-r1_ppt169_20260810/validation/ab_comparison_svg/ab_06_next_steps.png`
- P07：`/Users/muzi/Documents/ppt-master/skills/ppt-master/projects/router-regression-20260809/approval-native-a-r1_ppt169_20260810/validation/ab_comparison_svg/ab_07_support_asks.png`

### 结论：Router 零增益

结论只能是 **Router 零增益**。

- B1 的故事线和 A 基本相同：成效、机制、路径、保障、结语。
- B1 的主要关系类型在 A 中也会自然出现；Router 没有让 B1 在核心观点、事实证据、关系表达或跨页节奏上形成明显优势。
- B1 并未明显比 A 更差，尚不足以判为负增益；但新增 Director、Profile 和交接语义没有稳定转化为可见品质提升，因此也不能称为正增益。

## 唯一第一优先点（仅建议，尚未改代码）

把 Director 的页面计划从“内容导演 + 视觉语义标签”提升为“内容导演 + 页面级视觉导演”。每页在既有六字段的内容中必须能自然回答：

1. 第一视觉主角是什么；
2. 哪些信息退后；
3. 哪项数据、图片、截图、案例或流程承担证据角色；
4. 核心关系如何被视觉感知；
5. 这一页为什么应当不同于相邻页。

这不是要求 Router 编排坐标、尺寸或固定模板，也不是增加状态机/质量门禁；它是 Director 计划在交给 PPT Master 前应具备的最低页面视觉说明。下一轮应先以这一点改写一个失败页的 Director plan，再由原生 Stage 2 / Executor 生成可比 B2；在此之前不继续改 routing、scoring、Profile 或测试数量。

## 不属于 Router 的问题

- 原始材料没有提供可用的现场照片、办理截图、界面证据或结构化图表素材；“不使用外部图片”进一步缩小了可用视觉证据池。
- `government-report` 工作区不满足当前 PPT Master 4.4 模板契约，且 B1 没有安装后的模板产物；这是模板兼容/生产前提问题，不是 Router 路由问题。
- LibreOffice 实际 PPTX 渲染缺少 `Microsoft YaHei`，导致 A 和 B 的中文文字显示为方框；这是字体环境/交付验证问题，不属于 Router。
- 在已有清晰构图说明时，Executor 仍可能未充分实现细节（如 P01 的光束、P08 的首尾呼应）；这是 PPT Master Executor 的实现问题。
