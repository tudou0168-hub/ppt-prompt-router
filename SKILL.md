---
name: ppt-prompt-router
description: PPT Master 4.4+ 的专业导演路由与语义增强层；在专业导演确有增量价值时补充场景知识和六字段逐页语义，PPT Master继续负责完整原生生产流程。
version: 3.1.3
---

# PPT Prompt Router 3.1.3 Stable

## 核心执行偏好

**不考虑 Token、工具调用和思考次数，以最终汇报效果为优先，充分发挥 PPT Master 原生完整能力。**

Router 负责专业场景判断、内容导演和页面语义；PPT Master 负责顶层 Route、用户确认、模板应用、Strategist、Design Spec / Spec Lock、Executor、质量流程与导出。

## Default Generate 主流程

### 1. Router Preflight

先运行：

```bash
python3 scripts/route.py --phase preflight ... --json
```

得到 `FULL / LIGHT / BYPASS`、Primary Profile、可选 Secondary Lens、workspace intent 和非权威 Route Hint。已解析 Profile 时，`director_handoff.base_prompt` 已内联 Director Kernel、语义词汇、Primary Profile 与 Lens，Profile 选择与实际读取合并为同一交接结果。

### 2. PPT Master Stage 1

从 PPT Master 自己的 `SKILL.md` 启动，由当前 `workflows/routing.md` 确认最终 Route。Default Generate 按原生流程完成项目初始化、Communication Contract、Template Candidate Preparation 与 Stage 1确认。

精确 `workspace-root` 默认表达 `explicit_use_requested`：Stage 1 以该路径作为明确模板使用意图和候选输入，最终仍由 PPT Master 原生确认机制完成确认。

### 3. Director V15

Stage 1确认后，再运行同一个 `route.py`：

```bash
python3 scripts/route.py   --phase director   --prompt-id <preflight选中的profile_id>   --stage1-contract <confirmed-stage1-json-or-path>   --project-dir <project_path>   <保留原始任务、材料、workspace等参数>   --json
```

Router 在这一阶段只编译并返回 `director_handoff.inline_prompt`。当前主智能体以专业 Director 角色执行它，并实际生成：

`<project_path>/analysis/presentation_plan.md`

文件头记录 Router version、Profile、Profile SHA 与 Stage 1 SHA，便于项目审计。它不是 Router 的第二套内容生产器，也不新增状态机或独立质量门禁。逐页策划使用：

`page_role / audience_move / relationship / hierarchy / rhythm_intent / visual_semantics`

同时形成 Core message、页面 Content、Evidence / image material 与 Speaker Notes。

### 4. Strategist / Stage 2

Stage 2 从 `presentation_plan.md` 开始，并应用 `stage2_handoff.activation_prompt`：

- Visual Style 统一颜色、字体、线条、材质、图像处理、图标和整体气质；
- 页面空间结构由每页真实 `relationship / hierarchy / rhythm_intent / visual_semantics` 决定；
- 关系明确的页面先进行语义 Visualization Recall / 能力族召回，再选择候选、组合候选或自由设计；
- 卡片/面板服务等权并列、KPI、短清单和局部容器任务；递进、流程、汇聚、对比、层级、系统、主张-证据等关系使用相应结构或自由构图；卡片依赖、连续 dense 与构图重复只用于诊断，不设机械配额；
- Page Rhythm 综合页面角色、Audience Move、关系、信息密度和章节位置形成全篇节奏；
- 图片角色和位置随页面语义变化，形成侧证据、横幅、局部大图、背景图、小型佐证等不同角色。

Strategist 将这些语义与原始材料、用户确认、模板和当前项目共同形成完整 `design_spec.md`。

### 5. Design Spec / Spec Lock / Executor

Stage 2确认后按 PPT Master 原生机制完成 `design_spec.md`、`spec_lock.md`、资源获取与 Executor。

Executor 围绕 page-scale composition 先完成语义骨架，再充分发挥 Visualization、Native Shape、Charts / Diagrams、SVG、图片融合、数据表达、Visual Job Router、Live Preview 与当前页面适用的其他原生视觉能力。

### 6. Review / Export

继续采用 PPT Master 当前原生 Final Quality Check、Visual Review、Speaker Notes、后处理、Export 与 Postflight。

## 介入深度

- **FULL**：新生成或重构型专业汇报，包括政府年度/半年总结、政务专项汇报、经营分析、技术方案等。
- **LIGHT**：Quick、Beautify、需要先提炼内容的 Fill Native、明确专业场景的模板建设。
- **BYPASS**：Enhance Native、纯原生替换、纯模板提取、专业信号不足的模糊 PPT 请求。

## 26 个 Director Profile

`government_annual_summary` 专门服务政府机关年度总结、半年总结与阶段性总结。它与 `government_strategy` 分工：前者围绕“工作—成效—变化—下一步—问题建议”，后者围绕“责任/现状—差距—目标—建设路径—决策”。当政府 + 阶段总结语义明确且没有专项规划、建设方案、实施方案、战略规划或路线图等反证时，年度总结优先于泛化的“政府汇报”信号。

## 设计能力融合

`references/ppt_master_design_capability_map.md` 是 Stage 2 的语义能力地图，`references/ppt_master_4_4_mapping_protocol.md` 定义六字段二次编译和视觉激活边界。

**导演限定问题空间，Strategist限定设计空间，Executor完成视觉解。**
