# PPT Master v2.8 / v2.9 / v4.5 Visual DNA 考古报告

## 基线

| 实现 | 路径 / 标识 | 证据 |
| --- | --- | --- |
| v2.8 | `/Users/muzi/Documents/ppt-master-version-lab/ppt-master-v2.8.0` | archive v2.8.0；ZIP SHA-256 `14589dc5ad747200572ea3c19bb8ee4a3a8129041f1f6fd2bc8673e11e3273c3` |
| v2.9 | `/Users/muzi/Documents/ppt-master-version-lab/ppt-master-v2.9.0` | archive v2.9.0；ZIP SHA-256 `59f59e08934fddce3f0dc7a6697922505adaaa601ea7a1420adba2602b67a2c9` |
| v4.5 | `/Users/muzi/Documents/ppt-master/skills/ppt-master` | release tag / commit `ec824aecd551a0bc2990b617a131d907a5d808ea`；`SKILL.md` version `4.5.0` |

两个旧版包不含 Git 元数据，因此本报告只将它们称为 archive，不虚构 tag 或 commit。

## 链路差异

| 链路 | v2.8 / v2.9 | v4.5 | 结论 |
| --- | --- | --- | --- |
| 内容与叙事 | `executor-consultant-top` 把 SCQA、结论先行和数据语境直接写进角色。 | Strategist 已负责沟通合同、模式、设计规格和页面大纲。 | 保留“结论与证据关系”的判断；不要让 Executor 替代内容导演。 |
| 视觉推理 | General / Consultant / Top Consultant 以人格化角色缩小选择空间，直接给出层级、节奏、图表与构图经验。 | Mode、Visual Style、Structure、Visualization 等能力拆分为当前分支。 | 恢复通用视觉判断，不恢复角色化行业 Executor。 |
| 构图 | 旧版提供大量位置、尺寸、固定页面骨架和特定形状组合。 | `executor-structure` 提供关系原子、形状角色、构造顺序与验证。 | 保留“主空间表达真实关系”；淘汰坐标和固定骨架。 |
| 数据与证据 | Consultant Top 强调数据不孤立、比较基准和“so what”。 | Strategist、Chart、Table 分支可按对象选择表达并做验证。 | 保留证据贴近结论、图表/表格由问题决定。 |
| 图像 | 旧版列出大量图文构图模式，容易形成丰富但也可能装饰化的页面。 | v4.5 有图像分支、方向性多图构图和 Visual Job Router。 | 保留“图像承担证据或解释角色”；不把图片当节奏配额。 |
| 节奏 | General 明确 dense / breathing 交替，Top Consultant 提供结论页与高密度分析页差异。 | v4.5 已有 roster rhythm、page role 与页级 Composition。 | 保留故事驱动的节奏，不设每 N 页强制换形式。 |
| PNG QA | 旧版以静态 SVG 检查和角色自检为主。 | v4.5 有 SVG checker、Playwright PNG、Visual Review hard / soft rules。 | v4.5 是生产权威；PNG 目视是最终判断，不能被 0 errors 替代。 |

## 旧能力映射

| 旧能力 | 判断 | v4.5 推荐落点 |
| --- | --- | --- |
| 结论先行、Assertion Title | 保留 | Universal Visual Prior → Strategist |
| SCQA | 条件保留 | Narrative reasoning；仅适合问题—决策型故事 |
| Pyramid Principle | 保留思想 | 信息层级与证据组织 |
| 数据语境、比较基准、结论解释 | 保留 | Strategist + Chart / Table 分支 |
| Strategic Roadmap、架构、矩阵等视觉语言 | 保留词汇，不保留模板 | Structure / Visualization 由真实关系触发 |
| General 的节奏、重量、图文关系经验 | 保留 | Universal Visual Prior + roster rhythm |
| Consultant Top 固定顶部条、Takeaway Box | 不通用 | 仅作为语义强调的可选实现 |
| 固定 1280×720 坐标、列宽、卡片骨架 | 不保留 | — |
| “三项内容即三卡片”等安全构图 | 不保留 | — |
| 行业化 Executive 口吻 | Profile 相关 | Router Director / Speaker Notes |

## 推荐落点

第一轮以项目级、未注册 Style 工作区承载 Prior，验证它能否通过 v4.5 原生 Stage 1 / Stage 2 进入 Strategist，而不改变任何生产源码。

若同一 Prior 在五寨和跨类型样页中都带来可重复的视觉提升，正式建议是：把 Prior 提炼为 PPT Master Strategist 的通用设计参考；Router 仍只提供专业语义，Executor 仍只执行已确认的设计策略。若 Spec 正确而 PNG 仍失败，则问题属于 v4.5 Executor / Visual Review 上游，不用 Router 补偿。
