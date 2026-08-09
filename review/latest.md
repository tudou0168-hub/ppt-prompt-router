# 本轮审查交接

## 本轮目标

将 PPT Prompt Router 升级为 3.1.3：修正政府半年／年度总结场景的选择优先级，并固化 Router 作为“专业导演增强与交接层”的职责边界。

## 修改内容

- 调整 `scripts/scoring.py`：当政府域、阶段总结语义成立且没有规划建设反证时，优先 `government_annual_summary`。
- 调整 `scripts/route.py`：Stage 1 后只编译 Director handoff；明确当前主智能体作为 Director 实际生成 `analysis/presentation_plan.md`。
- 更新 Profile、映射协议、README、SKILL、安装版本和回归脚本。
- 新增依赖零的 `scripts/regression.py`，覆盖 Profile 路由、非默认路径和 Director handoff。
- 本文件仅用于 GitHub 研发审查；不参与 Router 生产运行。

## 测试

- `python3 scripts/regression.py`：通过，26 个 Profile、188 个路由案例、4 条非默认路径、Director handoff。
- `python3 -m py_compile scripts/*.py installers/*.py`：通过。
- `python3 -m json.tool prompt-index.json`：通过。
- 隔离真实项目验证：审批服务局完成 8 页完整 Router 样本；五寨规划、河南郑州差距分析、智能招生方案各完成一张高复杂度代表页。所有已生产 SVG 通过 final quality check，所有 PPTX 通过 delivery check。

## 关键证据

- 隔离项目根目录：`/Users/muzi/Documents/ppt-master/skills/ppt-master/projects/router-regression-20260809`
- 审批服务局完整 Router 样本：`approval-router-b-r1_ppt169_20260809`
- 审批服务局导出：`approval-router-b-r1_ppt169_20260809/exports/approval-router-b-r1_20260809_224240.pptx`
- 审批服务局 Contact Sheet：`approval-router-b-r1_ppt169_20260809/validation/contact_sheet.png`
- 完整研发验证说明：`docs/validation-report-3.1.3.md`

## 已知问题

- 原审批服务局原生 Master A 基线没有可导出的 PPTX，尚未形成同材料、同条件的 A/B 视觉对照。
- 审批服务局 Router 样本的导演结构和关系表达已验证，但视觉上仍偏同色与文本化，缺少业务场景证据图；后三份材料目前只验证代表页，不代表完整成册质量。
- 当前源码目录是发布包，不含 Git 元数据；推送将通过独立、干净的 Git 工作副本进行，避免覆盖本地旧工作副本中的无关未提交内容。

## 请 ChatGPT 独立评审的四个问题

1. **A/B 基线缺失**：原审批服务局项目只读保留，但没有原生 Master A 的可导出 PPTX。请给出最小可信补跑方案，明确输入、保持不变的条件、必需产物和人工对照维度。
2. **证据链强度**：当前用 `presentation_plan.md → design_spec.md → spec_lock.md → SVG / Contact Sheet / PPTX` 证明 Router 语义传递。请判断这是否足够轻量且可信；如不足，只提出不侵入生产流程的最小补证方式。
3. **真实样本代表性**：审批服务局已完成 8 页，另外三类材料仅完成最复杂、最易卡片化的代表页。请判断下一轮是补全整册，还是继续扩展高风险页面；给出选择标准，不要按页数机械凑产物。
4. **Router 与视觉问题的优先级**：现有视觉样本仍偏同色、文本化、场景证据不足。请区分哪些可能是 Router / Director handoff 问题，哪些属于 PPT Master 执行或素材问题，并给出按优先级排序的改进执行方案。

## 请 Reviewer 输出

- 对四个问题分别给出：结论、理由、最小可执行改动、验证方法与通过标准。
- 标明哪些建议应直接进入 Router，哪些只能作为 Director 或 PPT Master 的生产建议。
- 若建议与“Router 不生成计划、不接管 PPT Master、不增加生产状态机或质量门禁”的边界冲突，请明确指出并给出更轻的替代方案。

## 请 Reviewer 重点判断

1. Router 对 `government_annual_summary` 的优先级边界是否足够窄，是否会误伤建设规划或决策分析？
2. Router handoff 与 Director 实际产出计划的职责边界是否清楚，是否仍有 Router 变成第二套内容系统的风险？
3. 在没有原生 A 导出的情况下，最小可信 A/B 验证应如何补跑？
4. 下一阶段应优先修正 Router 逻辑，还是先补齐真实完整 PPT 生产基线与视觉评审？
