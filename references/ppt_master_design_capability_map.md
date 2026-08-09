# PPT Master 4.4 Design Capability Map

本文件服务 PPT Master Strategist的按需召回。Director先限定业务问题空间，Strategist再选择候选设计族，Executor完成最终视觉实现。

## 1. 语义召回决策树

1. 判断页面是否存在明确关系；普通并列信息直接进入观点、数据、图片、证据或自由构图。
2. 识别主要关系：流程、时间、递进、因果、对比、汇聚、发散、循环、层级、系统、证据等。
3. 明确信息主角：单一主角、多个等权、主张+多证据、路径+结果等。
4. 结合 `rhythm_intent`与全篇节奏，映射当前 Master的页面节奏。
5. 依据关系先召回少量候选能力族；关系明确的页面先完成召回，再决定采用候选、组合候选或自由设计。
6. 结合材料密度、页面角色、模板与视觉系统评估候选；自由设计始终是有效选择。
7. Executor完成 page-scale composition、形状、图片、图表和效果实现。
8. Visual Job Router依据成稿真实视觉问题补充焦点、边界、方向、融合、层次与可读性。

核心：**导演限定问题空间，Strategist限定设计空间，Executor完成视觉解。**

## 2. 关系 → 候选能力族

| Director关系 | Strategist优先搜索的候选族 |
|---|---|
| parallel | columns / pillars / separated regions / clean text groups |
| progression | stairs / ascending path / chevron / layered progression |
| causal | causal chain / flow / input-output |
| support | hub-spoke / pillars / hierarchy / pyramid |
| convergence | inward arrows / funnel / convergence composition |
| divergence | hub-spoke / radial / mind-map |
| process | process flow / numbered steps / chevron process |
| cycle | circular stages / wheel / feedback loop |
| time | timeline / roadmap / gantt |
| comparison | split / comparison / dumbbell / butterfly |
| hierarchy | hierarchy / pyramid / concentric |
| matrix | matrix / quadrant |
| system | ecosystem / hub / network / concentric / architecture |
| evidence | hero claim + proof regions / chart + interpretation / source evidence |
| none | free composition / typography / image / whitespace / simple grouping |

这些是候选族，而非页面模板指令。Strategist依据页面真实语义选择、组合或直接自由设计。

## 3. Page Rhythm

导演使用自然语言说明节奏意图，Strategist结合页面角色、Audience Move、真实关系、信息密度和章节位置完成翻译，让全篇形成自然的停顿、承载和舒展。常见语义对应：

- 阶段性成果、单一核心判断、章节关键停顿 → `anchor`候选；
- 多数据、多证据、多模块且逻辑清楚 → `dense`候选；
- 转折、少量内容、强调留白 → `breathing`候选。

## 4. Composition Geometry

Director只说明主次，例如单一主角、多项等权、多证据、主结论+支撑、路径+结果。Strategist据此选择 central hero、asymmetric split、evidence field、ascending path 等构图方向；Executor决定实际几何比例。Visual Style提供统一气质，页面构图保持逐页语义驱动。卡片/面板适合真正等权并列与局部容器任务，其他关系可使用对应结构族或自由构图。

## 5. Visualization Recall

将 `relationship`、页面角色、内容对象和数据形态转换为语义 tags，使用 PPT Master当前版本的 Visualization Recall / Catalog机制获得候选短名单，再结合页面语义决定采用、改造或自由设计。

## 6. Native Shapes / Charts / Tables / Image Composition

内容天然适合数据图表、表格、原生形状、图片证据或图文构图时，优先发挥 PPT Master 相应原生能力。图片角色和位置随页面任务变化，可承担侧证据、横幅、局部大图、背景锚点或小型佐证；具体资产、参数、裁切与 SVG 实现由当前 Master 决定。

## 7. SVG Effects + Visual Job Router

Executor先完成语义骨架与主要构图，再根据页面真实视觉状态选择焦点、边界、融合、方向、层次、可读性等视觉作用。Visual Job Router属于实现阶段的视觉增强器。

## 8. Cross-page / Animation

当用户任务或 Master原生状态触发连续动作、转场、Morph或动画时，Director可描述跨页认知节奏，Strategist与Executor按当前版本原生机制完成实现。

## 9. 原生权威

PPT Master当前 `SKILL.md`、routing、Strategist、Executor和 capability scripts始终是能力名、枚举、参数与执行时机的最终权威；本地图只提供语义召回方向。
