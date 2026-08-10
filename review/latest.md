# 审查交接：V15 path-only Direct Plan 与四类最小真实小样

## 本轮目标

将 Reviewer 提供、已在沙箱验证的 V15 Direct Plan 实现与 `58aa8ab` 对齐；随后按“小样、逐类、Fail Fast”纪律验证新 Prompt 和 fresh PPT Master 交接。Router 不修改 PPT Master，也不生成整套 PPT。

## 修改内容

- 机械同步 Reviewer 包中已变更的生产/运行文件：`scripts/route.py`、`scripts/regression.py`、`scripts/scoring.py`、`prompt-index.json`、`SKILL.md`、相关协议文档，以及 5 个 Direct Plan Prompt。
- 5 个 Prompt 均为 Reviewer 最终版本，未自行润色、压缩、扩写或重新加入页面示例。
- Direct Plan Director task 仅给出专业 Prompt、材料、模板/参考/workspace 路径、用户要求和 Plan 输出路径；已迁移 Profile 不叠加 Secondary Lens。
- Router → fresh PPT Master 仍只传类型化路径、用户明确约束和短 activation，不传 Router 内部上下文。

## 极简程序验证

- `python3 scripts/regression.py`：通过。
  - 6 条代表性路由；5 个 Direct Plan Profile；path-only Director；typed Master handoff；Prompt anti-anchoring；LIGHT/BYPASS/未迁移 Profile 无 Plan。
- `python3 -m py_compile scripts/route.py scripts/regression.py scripts/scoring.py scripts/semantics.py scripts/template_intent.py`：通过。
- `python3 -m json.tool prompt-index.json`：通过。
- 临时目录 `install.py install`、`install.py validate`，以及已安装副本 regression：均通过。

## 小样方法

每类任务先用 Router Preflight 和独立 Director 生成/人工检查 `presentation_plan.md`，仅在 Plan 正确后启动 fresh PPT Master。每个 Master Context 只收到材料路径、Plan 路径、模板/参考/workspace 路径、用户要求和短 activation。项目先由宿主通过 PPT Master 原生 `project_manager` 初始化并导入材料；这不是 Router 状态机或 bootstrap。

两次早期试运行被排除：一次把只有 `analysis/` 的空目录交给 Master、一次沿用了旧 Plan 页码；均为测试宿主错误，未修改 Router。随后均从 Router 入口重新执行。

## 真实证据与第一失真

| Profile | 真实材料 | 选择结果 / Plan | 代表页与理由 | 结果 / 第一失真 |
| --- | --- | --- | --- | --- |
| `government_strategy` | `/Users/muzi/Desktop/源文件/五寨县“人工智能+”规划方案20260609v1.0.docx` | 高置信度，Direct Plan，无 Lens；Plan 正确区分拟建内容、现状缺口和待决策事项。 | P04 现有基础/边界、P07 总体体系、P13 实施路径、P14 决策保障。 | **PASS**。SVG 质量 0 error；四张 PNG 已人工查看。无 Router / activation / Plan / Executor 阻断。 |
| `work_report` | `/Users/muzi/Downloads/新郑市智慧城市综合应用业务系统建设项目项目运维服务报告模板.docx` | 高置信度，Direct Plan，无 Lens；Plan 把模板空值、需求汇总与明细冲突、历史日期和客户协同缺失明确为证据边界。 | P02 结果证据、P05 已完成交付、P06 风险、P08 客户协同。 | **PASS**。四页 SVG/PNG 已人工查看；每页 0 error。P02 页脚边界由 Executor 修正后通过，非 Router 问题。 |
| `decision_meeting` | `/Users/muzi/Desktop/河南省、郑州市政务服务对标浙江经验的差距分析与提升建议.docx` | 高置信度，Direct Plan，无 Lens；Plan 未虚构多方案，转而呈现真实约束、可接受取舍、推荐路线和拍板动作。 | P05 刚性约束、P06 真实取舍、P07 推荐路线、P12 拍板动作。 | **PPT Master upstream**。四页 SVG 最终质量 0 error；Quick Look 将 16:9 SVG 错裁为 1280×1280，实时预览截图为空白，无法形成可信 PNG 视觉验收。立即停止。 |
| `product_technical` | `/Users/muzi/Desktop/第三方业务系统实现”免证办、全程网办“解决方案.docx` | 高置信度，Direct Plan，无 Lens；Plan 区分原案例历史成效与新项目承诺，未补造部署、接口、安全或验收指标。 | P04 场景、P07 架构边界、P10 数据接口、P12 实施验收价值。 | **PPT Master upstream**。P07 页眉说明文字超出 `header` 边界 12.3%；在 Plan/Spec 正确后首次出现在 Executor/SVG 检查，按 Fail Fast 未修复、未生成 PNG、未导出。 |

## 关键本地路径

PR 可下载的汇总证据包：`review/artifacts/v15-path-handoff-small-sample-20260810.zip`；内容说明见同目录 Markdown。

- 政府战略 Plan：`/Users/muzi/Documents/ppt-master/skills/ppt-master/projects/router-regression-20260809/v15-government-strategy-rerun_ppt169_20260810/analysis/presentation_plan.md`
- 政府战略 PNG：`/Users/muzi/Documents/ppt-master/skills/ppt-master/projects/router-regression-20260809/v15-government-strategy-rerun_ppt169_20260810/previews/`
- 工作汇报 Plan：`/Users/muzi/Documents/ppt-master/skills/ppt-master/projects/router-regression-20260809/v15-work-report_ppt169_20260810/analysis/presentation_plan.md`
- 工作汇报 PNG：`/Users/muzi/Documents/ppt-master/skills/ppt-master/projects/router-regression-20260809/v15-work-report_ppt169_20260810/validation/previews/`
- 决策会 SVG / 质量：`/Users/muzi/Documents/ppt-master/skills/ppt-master/projects/router-regression-20260809/v15-decision-meeting_ppt169_20260810/svg_output/`、`/Users/muzi/Documents/ppt-master/skills/ppt-master/projects/router-regression-20260809/v15-decision-meeting_ppt169_20260810/validation/svg_quality_report.json`
- 技术方案 SVG / P07 报告：`/Users/muzi/Documents/ppt-master/skills/ppt-master/projects/router-regression-20260809/v15-product-technical_ppt169_20260810/svg_output/`、`/Users/muzi/Documents/ppt-master/skills/ppt-master/projects/router-regression-20260809/v15-product-technical_ppt169_20260810/validation/p07_sample_quality.json`

## 已知问题与边界

- 决策会的预览问题和技术方案的 SVG 文字边界问题均在 PPT Master Executor / Preview 层首次发生。没有证据支持通过修改 Router routing、Prompt、Plan、字体规则、几何规则或页面模板来绕过它们。
- 仅政府战略与工作汇报能形成可信 PNG 的视觉小样通过；决策会和技术方案不能宣称最终视觉验收通过。
- 这不是整套 PPT 验收：没有生成整套页面或 PPTX。

## 请 Reviewer 重点判断

1. 是否同意：四个 Direct Plan Profile 的 Router 层已完成可继续迁移所需的最小因果验证；其中两个失败应独立升级为 PPT Master 上游问题，而非要求重写 Prompt？
2. 是否同意项目初始化属于宿主的普通项目准备，Router 无需为此新增 bootstrap 状态、字段或协议？
3. 请审计 `scripts/route.py` 的 path-only Director / typed Master handoff 是否仍存在内部上下文泄漏或不必要字段。
4. 在 PPT Master 修复预览与 SVG 边界问题前，是否应暂停下一批 Profile 迁移，而不是扩增 Router 测试量？
