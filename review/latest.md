# 审查交接：Semantic Adapter 最小因果验证

## 本轮目标

只验证 `presentation_plan.md` 的纯演示语义能否被 fresh PPT Master 的 Strategist 消费并转化为可靠的页面设计判断。不是迁移新 Profile，也不是精修某一页，更不修改 PPT Master。

## 修改内容

- 5 个 Direct Plan 专业 Prompt（年度总结、政务规划、工作汇报、决策会、产品技术）删除所有下游实现耦合；Prompt 只保留专业内容分析、故事组织、逐页演示语义导演和统一的 `presentation_plan.md` 输出边界。
- `references/ppt_master_4_4_mapping_protocol.md` 改为 Master 侧的薄协议：页面任务、核心观点、内容关系、信息主次、表达意图、可用素材如何成为原生设计意图；不规定具体版式、图形、坐标、字体、颜色或 SVG。
- `master_handoff.activation_prompt` 只新增一条语义激活：将 Plan 的页面任务、核心观点、内容关系、信息主次和表达意图作为 Strategist 输入。
- 最小 regression 增加静态边界：5 个专业 Prompt 禁止出现 `PPT Master`、`design_spec`、`Stage 2`、`Spec Lock`、`Executor`、`§IX`、`§VIII` 及其他下游实现词。

## 测试

- `python3 scripts/regression.py`：通过（6 条代表路由、5 个 Direct Plan Profile、path-only Director、typed Master handoff、LIGHT/BYPASS/未迁移 Profile 无 Plan）。
- `python3 -m py_compile scripts/route.py scripts/regression.py scripts/scoring.py scripts/semantics.py scripts/template_intent.py`：通过。
- `python3 -m json.tool prompt-index.json`：通过。
- 临时安装目录执行 `install.py install`、`install.py validate` 及安装副本 regression：通过。

### 五寨县三页新项目盲测

材料：`/Users/muzi/Desktop/源文件/五寨县“人工智能+”规划方案20260609v1.0.docx`
项目：`/Users/muzi/Documents/ppt-master/skills/ppt-master/projects/router-regression-20260809/v15-semantic-adapter-government-strategy_ppt169_20260810`

Preflight 的 `government_strategy` 与 `planning_proposal` 并列，按本任务“面向领导的政务建设规划与决策沟通”人工仲裁为 `government_strategy`；不改 scoring。独立 Director 重新生成 15 页 Plan；fresh Master Context 只收到材料路径、Plan 路径、用户要求和短 activation。未传递 Router Prompt、Profile、Kernel、Lens、scoring 或此前 Context。

只生成实际 Plan 中选出的三页，未生成整套、未导出 PPTX：

| 页面 | Plan → Spec → Lock | PNG 实际审阅 | 首次失真 | 责任判断 |
| --- | --- | --- | --- | --- |
| P05 现有基础判断 | 保留“规划依托可确认 / 现状底数待核实”的事实边界与主次。 | 页码标签压住主标题。 | SVG/PNG | PPT Master Executor |
| P08 总体体系 | 保留“三类业务能力由统一智能底座承接”的主空间关系。 | 底座内左右平台说明文字彼此重叠。 | SVG/PNG | PPT Master Executor |
| P13 推进路径建议 | 保留“核实—试点—评估回看—扩展”的时序、门槛与风险保障。 | 阶段正文与“形成成果”行重叠，页码标签压住标题。 | SVG/PNG | PPT Master Executor |

SVG 结构检查是 0 errors、3 项 CJK 可测性 warnings；但 PNG 肉眼审阅不通过，不能以结构检查替代视觉验收。

## 关键证据

- Director Plan：`.../analysis/presentation_plan.md`
- Master Design Spec：`.../design_spec.md`
- Master Spec Lock：`.../spec_lock.md`
- PNG：`.../.preview/05_现有基础判断.png`、`.../.preview/08_总体体系.png`、`.../.preview/13_推进路径建议.png`
- SVG 质量报告：`.../validation/svg_quality_report.json`
- 可下载证据包：`review/artifacts/semantic-adapter-wuzhai-small-sample-20260810.zip`

## 已知问题

本轮没有发现 Prompt、Plan 或 Plan → Strategist 翻译首次失真；三页均在 Executor/SVG 文字几何阶段首次出现可见重叠。按 Fail Fast 规则，未对页面做项目专用修补，未执行工作汇报的跨场景测试，也未修改 Router 以掩盖 Master 的执行层问题。

## 请 Reviewer 重点判断

1. 是否同意：当前证据支持“语义 Adapter 已被 Strategist 消费”，但不能支持“最终三页视觉通过”；下一步应由 PPT Master 修复文字排版/几何质量，而不是继续改 Router Prompt？
2. 是否同意：在代表页出现 Master Executor 首次失真后，停止工作汇报跨场景测试符合因果实验纪律？
3. 请审查五个 Prompt 的下游耦合是否已清除，以及最小 activation 是否仍保持路径式、无内部上下文泄漏。
