# PPT Master 4.5 Universal Visual Prior 哨兵实验

## 结论先行

本轮不能宣布 Universal Professional Presentation Visual Prior 有效，也不能进入跨类型验证。

同一份冻结 Director Plan 在 P08、P05 上能让 PPT Master 4.5 输出可读、无硬缺陷的代表页；C（实验 Prior）在 P08 的“场景—能力—共同依赖”表达比 B 更明确。但 C 的 P13 在真实 PNG 中出现 `GATE 03` 条件文字被第 04 阶段面板遮挡的硬缺陷。静态 SVG 检查为 0 error / 0 warning，仍未发现此问题。按哨兵规则，本轮在此停止：不进入三类跨类型样页，不改 Router，不用页面专用规则补偿。

## 固定基线与证据身份

| 对象 | 固定身份 | 证据 |
| --- | --- | --- |
| Router 程序 | `075f987`（之后仅增加本轮文档、实验工作区与证据，不修改 Router 产品代码） | 当前 PR 分支 `agent/router-3.1.3-stable-review` |
| PPT Master 生产权威 | `/Users/muzi/Documents/ppt-master/skills/ppt-master`，`SKILL.md` 版本 `4.5.0`，release commit `ec824aecd551a0bc2990b617a131d907a5d808ea` | 完整运行时文件清单 `review/artifacts/v45-universal-prior-wuzhai/ppt-master-v4.5-file-list.txt`（19,852 项，SHA-256 `d5663c7866a07d501e47eb9bc9108b838343da5283ecbf7c35f25a55ac8aed19`） |
| v2.8 只读参考 | archive v2.8.0，非 tag/commit | ZIP SHA-256 `14589dc5ad747200572ea3c19bb8ee4a3a8129041f1f6fd2bc8673e11e3273c3` |
| v2.9 只读参考 | archive v2.9.0，非 tag/commit | ZIP SHA-256 `59f59e08934fddce3f0dc7a6697922505adaaa601ea7a1420adba2602b67a2c9` |

旧版能力差异、保留/淘汰映射见 [PPT Master Visual DNA 考古报告](ppt-master-visual-dna-archaeology.md)。九项不带坐标和模板的通用判断见 [Universal Professional Presentation Visual Prior](universal-professional-visual-prior.md)。

## 实验设计

- 材料：`/Users/muzi/Desktop/源文件/五寨县“人工智能+”规划方案20260609v1.0.docx`。
- Router 从入口运行。`government_strategy` 与 `planning_proposal` 在 preflight 同分；基于“政务、领导、规划决策沟通”人工仲裁为 `government_strategy`，没有改动 routing/scoring。
- 独立 Director Context 仅读取 Profile、材料和用户任务，生成 15 页 [冻结 Plan](../review/artifacts/v45-universal-prior-wuzhai/plan/presentation_plan.md)，SHA-256 `5848bd2a603dc69e111247c29d6cbc06ffee276871facac6b9ff33e001754dbf`。
- B 与 C 每页均为 fresh PPT Master Context；只得到材料路径、同一 Plan 路径、用户任务及简短 activation。未得到 Router Prompt、Profile、Kernel、Lens、scoring、Capability Map 或对话历史。
- B：PPT Master 4.5 原生自由设计。C：同一流程，仅在 Stage 1 显式安装未注册的 [实验 Style 工作区](../review/experiments/universal-professional-visual-prior-style/templates/design_spec.md)。该工作区不含品牌、固定版式、SVG 原型或项目页表。
- 在 `router-regression` 中以用户已授权的委托方式完成 Stage 1/2；生产环境确认机制没有改变。
- 哨兵顺序：P08 → P05 → P13。每个条件只生成当前一页，不生成整套、Contact Sheet 之前不导出 PPTX。

## A / B / C 的比较边界

A 是用户指定的 `五寨县人工智能+政务服务规划方案_15页_Router21.pptx`：P07 对照本轮 P08 的“总体/能力结构”角色，P14 对照 P13 的“推进路径”角色，P05 仅作诊断页参考。A 与本轮材料、事实内容并不相同，因此只用于定性 Visual DNA 参照，不进入逐页量化评分。

本机 LibreOffice 对 A 的中文字体替代不完整，不能把该渲染结果当成精确视觉基准；A 的角色映射、页面结构和原始 PPTX 是参考证据。B/C 的比较则是严格的同 Plan、同材料、同约束、fresh Master 对照。

## 实际 PNG 审阅与评分

评分是人工审阅辅助记录，不是自动质量门。维度为：事实边界 20、核心观点/真实关系 25、信息层级/证据角色 20、整页空间动作/节奏 15、最终 PNG 执行 20。硬缺陷页的“最终 PNG 执行”记 0；静态 0 error 不可替代 PNG 结论。

| 页 | 条件 | 人工分 / 100 | PNG 首次读取 | 静态与 Visual Review | 首次失真 |
| --- | --- | ---: | --- | --- | --- |
| P08 智能办事 | B 原生 | 85 | 四组办事能力汇聚到共同依赖闸门；关系可读，但四卡的权重差较弱。 | 静态 0 error / 0 warning；PNG 通过，无修改。 | 无 |
| P08 智能办事 | C Prior | 91 | 标题先给出“先验证闭环”，路径、重点能力和共同依赖带形成明确阅读顺序。 | 静态 0 error、1 条 CJK 估算提示；PNG 通过，无修改。 | 无 |
| P05 差距核验 | B 原生 | 92 | 三端核验对象汇入共同最小输出，再进入试点排序，决策收束强。 | 初检 5 个文字边界问题，经 Executor 同轮修复；最终静态 0 error / 0 warning；PNG 通过。 | 无（修复后验证） |
| P05 差距核验 | C Prior | 89 | “服务诉求”与“本地待测问题”清楚区分，底部核验输出形成事实边界；三段仍较接近等权。 | 静态 0 error、1 条 CJK 估算提示；PNG 通过，无修改。 | 无 |
| P13 推进路径 | B 原生 | 93 | 四阶段、进入条件、右侧推进边界与评估回返线完整可读。 | 静态 0 error、1 条 tspan 估算提示；PNG 通过，无修改。 | 无 |
| P13 推进路径 | C Prior | 72 | 计划与 Spec 正确强调阶段闸门和反馈；但 `GATE 03` 条件被第 04 阶段面板遮挡，扩展条件无法完整读取。 | 静态 0 error / 0 warning；PNG Visual Review H6 hard，停止、未修复。 | Executor / SVG 几何 |

### 逐页因果判断

| 页 | Plan → Spec 是否保留语义 | PNG 结论 | 责任判断 |
| --- | --- | --- | --- |
| B P08 | 是：场景能力与共同前置依赖被翻译为双层关系。 | 通过。 | 无首次失真。 |
| C P08 | 是：Plan 的“高频、规则清晰、先验证闭环”成为第一眼焦点。 | 通过。 | 无首次失真。 |
| B P05 | 是：三端问题—核验对象—共同输出—排序动作完整。 | 通过；初始几何问题在同轮静态修复。 | 无首次失真。 |
| C P05 | 是：服务诉求与待核验事实边界完整。 | 通过。 | 无首次失真。 |
| B P13 | 是：时序、闸门、反馈和不预设日期/预算完整。 | 通过。 | 无首次失真。 |
| C P13 | 是：Spec 明确要求 Gate 03 在扩展前可见。 | 失败：Gate 03 文本被 Stage 04 面板遮挡。 | PPT Master Executor / SVG 几何；不是 Router、Director、Prior 或 Visual Review 的可原子修复问题。 |

## 产物

- B/C 并排三页 Contact Sheet：[B-vs-C-contact-sheet.png](../review/artifacts/v45-universal-prior-wuzhai/B-vs-C-contact-sheet.png)
- B Contact Sheet：[B/contact-sheet.png](../review/artifacts/v45-universal-prior-wuzhai/B/contact-sheet.png)
- C Contact Sheet（含 P13 硬缺陷）：[C/contact-sheet.png](../review/artifacts/v45-universal-prior-wuzhai/C/contact-sheet.png)
- A 的角色映射参考（P05/P07/P14）及 A P07 → C P08 并排图：[A/](../review/artifacts/v45-universal-prior-wuzhai/A/)；文件名已标明 `renderer-limited`，不得用于逐页量化评分。
- 全部 Plan、Spec、Lock、SVG、静态报告、Visual Review 前后 PNG 和 finding：`review/artifacts/v45-universal-prior-wuzhai/`。

## 停止结论与下一步

实验 Prior 具有值得保留的假设：它在 P08 中帮助 Strategist 把真实关系、主次与共同依赖写入 Spec，而没有把它变成 Router Profile 或第二套 Executor。但 C 的三页没有全部通过，因此尚不能把它建议为 PPT Master 的正式通用参考，也不能声称其在跨项目稳定增益。

唯一应优先处理的问题是：PPT Master 需要在 SVG/PNG 层增加或修复“相邻模块遮挡闸门/条件文本”的几何回归能力。该问题应由 PPT Master upstream 独立处置；本 PR 不修改其源码。修复后应以**同一冻结 Plan、同一 C P13、fresh Master Context**复跑，再决定是否进入 product_technical、data_report、business_proposal 三类样页。不得通过修改 Router Profile、加入页面专用规则或放宽检查来绕过失败。
