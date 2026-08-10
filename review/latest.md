# 审查交接：4 个 Direct Plan Prompt 原样迁移与中止盲测的故障证据

## 本轮目标

将 Reviewer 已定稿的 4 个专业 Prompt 原样接入 `direct_plan_v1`，验证 Router 的协议登记和路径式交接。真实盲测用于暴露程序问题，不用于精修任何单个项目页面。

## 修改内容

- 以下 4 个 Prompt 已从用户提供的压缩包逐字覆盖，未作润色、压缩或重构：
  - `government_strategy`
  - `work_report`
  - `decision_meeting`
  - `product_technical`
- `prompt-index.json` 仅按 `REGISTRY_PATCH.md` 修改 5 个 Profile 的 `profile_version: 3.1.3` 与 `director_protocol: direct_plan_v1`；没有修改 routing signals、scoring、conflicts、lens、maturity 或 Router 主流程。
- 回归增加了 5 个已迁移 Profile 的协议断言，并将原“未迁移 Profile”断言移至仍未迁移的 `business_proposal`。

## 程序测试

- `python3 scripts/regression.py`：通过（26 Profile、188 路由案例、4 非默认路径、5 Direct Plan Profile）。
- `python3 -m py_compile scripts/route.py scripts/regression.py scripts/scoring.py scripts/semantics.py scripts/template_intent.py`：通过。
- `python3 -m json.tool prompt-index.json`：通过。
- 临时目录执行 `python3 install.py install` 与 `python3 install.py validate`：通过。

## Direct Plan 注册状态

| Profile | profile_version | director_protocol |
| --- | --- | --- |
| `government_annual_summary` | `3.1.3` | `direct_plan_v1` |
| `government_strategy` | `3.1.3` | `direct_plan_v1` |
| `work_report` | `3.1.3` | `direct_plan_v1` |
| `decision_meeting` | `3.1.3` | `direct_plan_v1` |
| `product_technical` | `3.1.3` | `direct_plan_v1` |

LIGHT、BYPASS 与未迁移 Profile 仍是无 Plan 的 fresh Master 路径。

## 已发现的真实问题与证据

用户已要求停止四份 PPT 的全量测试；因此以下是已产生的 SVG 质量证据，不是完整 PPTX、Contact Sheet 或最终视觉结论。没有任何一项可被解读为 Prompt 已通过视觉质量验收。

| 任务 | 已执行到的阶段 | 发现的问题 | 初步责任归属 |
| --- | --- | --- | --- |
| 政府专项规划（15 页） | SVG 生成与 SVG 质量检查 | P05、P12 标题分别发生 2.0% 和 1.6% 水平越界；P01 有未能解析的文本几何告警。 | PPT Master Executor / SVG 排版，不足以归因于 Director Prompt。 |
| 企业运维工作汇报（8 页） | SVG 生成、首屏与全量质量检查 | 首屏制作中发现主模块边界、文字越界和字号锚点问题，Master 已在生成过程中修正；最终 SVG 报告为 8/8、0 warning、0 error。原材料是未填完整数据的报告模板，Plan 没有虚构数值。 | 已修复的 Master 执行问题；材料数据不足不是 Router 问题。 |
| 政务决策会（12 页） | SVG 生成与 SVG 质量检查 | 7 页 warning：文本根几何不可验证，以及多个段落被拆成兄弟 `<text>`，使质量检查无法稳定验证段落边界。 | PPT Master Executor / SVG 语义与质检契约；不是 Profile 选择问题。 |
| 技术解决方案（12 页） | SVG 生成与 SVG 质量检查 | 仅 1/12 通过、19 error：标题/正文越界、未声明的字号重复、插图锁定条目重复或模式不匹配、viewBox 问题。 | 明确是 PPT Master Executor/素材锁定链路问题；尚无证据表明应改 Prompt。 |

对应本地证据路径（原始材料不随 PR 上传）：

- `/Users/muzi/Documents/ppt-master/skills/ppt-master/projects/router-regression-20260809/blind-government-strategy_ppt169_20260810/validation/svg_quality_report.json`
- `/Users/muzi/Documents/ppt-master/skills/ppt-master/projects/router-regression-20260809/blind-work-report_ppt169_20260810/validation/svg_quality_report.json`
- `/Users/muzi/Documents/ppt-master/skills/ppt-master/projects/router-regression-20260809/blind-decision-meeting_ppt169_20260810/validation/svg_quality_report.json`
- `/Users/muzi/Documents/ppt-master/skills/ppt-master/projects/router-regression-20260809/blind-product-technical_ppt169_20260810/validation/svg_quality_report.json`

## 已知边界

- 这轮已按用户要求中止，未导出 PPTX、PNG 或 Contact Sheet，不能据 SVG 结构质量替代人工视觉审阅。
- 因没有形成同条件、完整的最终成品，不能据此宣称任何新 Prompt 提升或降低 PPT 的最终视觉质量。
- 4 个 Prompt 必须保持 Reviewer 定稿原文；在 Reviewer 明确提出跨项目、可复现的 Director 问题前，不应基于上述页面现象改写它们。

## 请 Reviewer 审核并给出方案

1. 请判断这些失败是否应全部先归入 PPT Master Executor／SVG 质量链路，而非要求改写 4 个 Direct Plan Prompt；如不同意，请指出能证明 Prompt 造成问题的具体证据。
2. 请审计当前 `direct_plan_v1` 的协议登记和路径交接，确认 4 个 Prompt 是否已被正确、最小化地接入，且没有将 Router 内部上下文泄漏给 Master。
3. 请提出一个**不生成整套 PPT** 的最小代表页因果验证方案：每个场景选哪些页面角色、应保留哪些原生阶段、以及什么证据足以区分 Director、Master Strategist、Executor 与素材问题。
4. 请指定下一项唯一优先修复点；不要建议因单页颜色、形状、卡片等偶发现象改写专业 Prompt。
