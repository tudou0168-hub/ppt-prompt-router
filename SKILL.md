---
name: ppt-prompt-router
description: PPT Master 4.4+ 的专业导演路由层；根据真实任务选择专业 Prompt，在独立 Router Context 生成 presentation_plan.md，再通过严格路径式交接启动 fresh PPT Master Context。
version: 3.1.3
---

# PPT Prompt Router 3.1.3 Stable

Router 负责：判断任务场景、选择专业 Profile、在已迁移的 Direct Plan 场景中生成 `presentation_plan.md`。

PPT Master 负责：最终 Route、Stage 1/2、模板处理、Strategist、Design Spec / Lock、Executor、Visualization、Native Shape、SVG、Charts / Diagrams、图片、Live Preview、动画/转场、Review、Export、Postflight 以及当前任务实际命中的其他原生能力。

## 核心原则

1. 用户明确要求 → 原始事实材料 → 用户明确模板/参考要求 → Profile 默认经验。
2. Router 与 PPT Master 使用 fresh context，通过**路径**交接，不传 Router conversation、Profile 全文、Kernel、scoring、capability map 或调试历史。
3. `presentation_plan.md` 负责“讲什么、为什么讲、真实关系、信息主次和表达意图”；具体页面设计由 PPT Master 自主完成。
4. 发现用户实质改变核心任务、材料范围或页面规模时，从 Router 入口重新生成 Plan，再启动新的 Master Context。

## Direct Plan 主流程

1. Preflight：

```bash
python3 scripts/route.py --phase preflight ... --json
```

得到 `FULL / LIGHT / BYPASS`、Primary Profile、`execution_path` 和非权威 Master Route Hint。

2. 仅当 `execution_path.requires_presentation_plan=true` 时，在独立 Router Director Context 运行：

```bash
python3 scripts/route.py \
  --phase director \
  --prompt-id <profile_id> \
  --project-dir <project_path> \
  --material <source_path> \
  --user-request <user_request> \
  --json
```

`director_task.task.prompt` 只提供专业 Prompt 路径、材料路径、模板/参考路径、用户要求和输出路径。Director 自己读取这些路径，直接写入：

`<project>/analysis/presentation_plan.md`

完成后结束 Router Context。

3. 启动 fresh PPT Master Context，只交接：

- `material_paths`
- 可选 `presentation_plan_path`
- `template_paths`
- `reference_paths`
- `workspace_roots`
- 原始用户任务和明确约束
- 简短 `activation_prompt`

PPT Master 从当前 `SKILL.md` 开始，按当前版本原生流程生产。

## 已迁移 Direct Plan Profiles

- `government_annual_summary`
- `government_strategy`
- `work_report`
- `decision_meeting`
- `product_technical`

以上 Profile 统一采用 V15 的自然语言页面导演结构：

- 页面任务
- 核心观点
- 内容关系
- 信息主次
- 表达意图
- 页面内容
- 可用素材
- Speaker Notes

专业方法由各 Profile 自己定义；不使用固定页面示例、固定页码或固定版式引导 Agent 模仿。

## 介入深度

- **FULL + Direct Plan Profile**：Router Director → `presentation_plan.md` → fresh PPT Master。
- **FULL + 未迁移 Profile**：fresh PPT Master，无 Plan，状态为 `not_migrated`。
- **LIGHT**：fresh PPT Master，无 Plan。
- **BYPASS**：fresh PPT Master，无 Plan。
