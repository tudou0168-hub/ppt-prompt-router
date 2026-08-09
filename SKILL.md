---
name: ppt-prompt-router
description: PPT Master 4.4+ 的专业导演路由层；在独立 Router Context 中生成专业 `presentation_plan.md`，然后以严格路径式交接启动全新 PPT Master Context。
version: 3.1.3
---

# PPT Prompt Router 3.1.3 Stable

Router 是专业导演增强层，不是第二套 PPT 生成系统。Router 负责场景判断；仅当选中的 Profile 明确声明 `director_protocol: direct_plan_v1` 时，才在独立上下文中直接生成 `presentation_plan.md`。PPT Master 继续负责其原生 Route、确认、Strategist、Design Spec / Lock、Executor、质量流程和导出。

## Default Generate 主流程

1. Router Preflight：运行 `python3 scripts/route.py --phase preflight ... --json`，得到 `FULL / LIGHT / BYPASS`、Primary Profile、`execution_path` 和非权威 Master Route Hint。
2. 只有 `execution_path.requires_presentation_plan=true` 时，宿主才准备普通 `<project>/analysis/` 工作目录，并以独立 Router Director Context 运行：

```bash
python3 scripts/route.py \
  --phase director \
  --prompt-id <preflight选中的profile_id> \
  --project-dir <project_path> \
  --material <原始材料路径> \
  --user-request <简洁用户要求> \
  --json
```

`director_task.task.prompt` 仅供这一个 Router Context 使用。它读取对应专业 Prompt 和原始材料，直接写入 `<project>/analysis/presentation_plan.md` 后结束；不生成 Design Spec、Spec Lock、SVG、图片或 PPTX。

3. 启动**全新** PPT Master Context。只传递 `master_handoff` 的 `material_paths`、可选 `presentation_plan_path`、`template_paths`、`reference_paths`、`workspace_roots`、用户明确要求和短激活提示。不得把 Router conversation、Director Kernel、Profile、Lens、semantic vocabulary、scoring、capability map 或调试日志传入。
4. 新 Context 从 PPT Master 当前 `SKILL.md` 开始，按它实际命中的原生流程执行。存在计划时直接读取它；不存在计划时不得传递虚构路径，也不得要求 Master 创建第二份计划。

只有当 Master Stage 1 实质改变核心任务、材料范围或页面规模时，才停止当前 Master Context，重新启动独立 Router Context 更新计划，再启动新的 Master Context。普通确认不触发回流。

## Reference Implementation

`government_annual_summary` 是首个 Direct Plan Profile，注册表标识为 `director_protocol: direct_plan_v1`。它直接使用“页面任务、核心观点、内容关系、信息主次、表达意图、页面内容、可用素材、Speaker Notes”写计划，并给出成果数据、改革机制、下半年路径和问题建议的完整页面导演示例。

其他 Profile 保留现有专业知识，但尚未逐个升级为 reference 级别的完整页面导演 Prompt；它们在完成自身迁移与真实验证前不产生 Plan，直接以类型化路径交接启动 fresh Master。

## 介入深度

- **FULL + Direct Plan Profile**：Router Director → Plan → fresh PPT Master。
- **FULL + 未迁移 Profile**：fresh PPT Master，无 Plan；Router 标明 `not_migrated`，不把旧 Profile 伪装成新协议。
- **LIGHT**：fresh PPT Master，无 Plan。
- **BYPASS**：fresh PPT Master，无 Plan。

所有 Profile 都先服从：用户明确要求 → 原始事实材料 → 用户明确模板／参考要求 → Profile 专业默认经验。
