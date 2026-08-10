# 审查交接：PPT Master 4.5 Universal Visual Prior 哨兵实验

## 本轮目标

验证一个未注册、可撤销的通用 Visual Prior 能否通过 PPT Master 4.5 原生 Stage 1/Strategist 改善关系、层级、证据和跨页节奏；不改 Router 产品代码、routing/scoring/Profile，也不改 PPT Master 源码。

## 修改内容

- 新增 v2.8 / v2.9 / v4.5 Visual DNA 考古报告与保留/淘汰映射。
- 新增九项 Universal Professional Presentation Visual Prior。
- 新增仅含沟通方法、通用视觉判断和 Review Focus 的未注册实验 Style 工作区；v4.5 原生 Style 契约已通过。
- 未修改 Router 路由、评分、Profile 或 PPT Master 源码。

## 测试

- v2.8、v2.9 仅作只读考古；已记录 ZIP SHA-256、archive 身份和 v4.5 文件清单。
- Router 从入口选择 `government_strategy`（与 `planning_proposal` 同分后按政务领导决策沟通人工仲裁），独立 Director 生成并冻结 15 页 Plan。
- B/C 每页均用 fresh Master Context 和相同 Plan，仅 C 在 Stage 1 显式安装实验 Style：P08 → P05 → P13。
- P08、P05 的 B/C PNG 均通过；C P13 的静态 SVG 检查 0 error/0 warning，但 PNG 中 `GATE 03` 条件文本被第 04 阶段面板遮挡，Visual Review H6 hard。
- 按 fail-fast，停止于 C P13；未进入跨类型验证，未生成整套或 PPTX。

## 关键证据

- 详细报告：[docs/v45-universal-prior-validation.md](../docs/v45-universal-prior-validation.md)
- 冻结 Plan、B/C Spec/Lock/SVG/PNG/Review：[review/artifacts/v45-universal-prior-wuzhai/](artifacts/v45-universal-prior-wuzhai/)
- 重点对照：[B-vs-C-contact-sheet.png](artifacts/v45-universal-prior-wuzhai/B-vs-C-contact-sheet.png)
- C P13 硬缺陷：[C/P13/after.png](artifacts/v45-universal-prior-wuzhai/C/P13/after.png)，[finding](artifacts/v45-universal-prior-wuzhai/C/P13/visual_review.json)

## 已知问题

目前证据只能说明 Prior 在 P08 的 Strategist 语义表达上有可解释的正向变化；不能证明跨页、跨类型稳定增益。P13 的首次失真发生在 PPT Master Executor / SVG 几何，不应由 Router 补偿。

## 请 Reviewer 重点判断

1. 是否同意 C P13 的 H6 遮挡属于 PPT Master upstream Executor 几何问题，而非 Router、Direct Plan 或 Prior 的页面专用缺口？
2. 是否同意在同一冻结 Plan 的 C P13 未通过前，停止 Profile 扩展与跨类型样页符合实验纪律？
3. 是否同意后续先修复/验证 PPT Master 的文字与相邻模块遮挡回归，再以同一 C P13 fresh context 复跑，而不是修改 Router 或 Style 来回避失败？
