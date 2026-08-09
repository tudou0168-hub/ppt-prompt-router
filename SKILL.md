---
name: ppt-prompt-router
description: PPT Master 4.4+ 的专业导演路由层；在独立 Router Context 中生成专业 `presentation_plan.md`，然后以严格路径式交接启动全新 PPT Master Context。
version: 3.1.3
---

# PPT Prompt Router 3.1.3 Stable

Router 是专业导演增强层，不是第二套 PPT 生成系统。Router 负责场景判断、选择专业 Profile，并在自己的独立上下文中直接生成 `presentation_plan.md`；PPT Master 继续负责其原生 Route、确认、Strategist、Design Spec / Lock、Executor、质量流程和导出。

## Default Generate 主流程

1. Router Preflight：运行 `python3 scripts/route.py --phase preflight ... --json`，得到 `FULL / LIGHT / BYPASS`、Primary Profile 和非权威 Master Route Hint。
2. 对 FULL 专业导演任务，宿主只需准备普通 `<project>/analysis/` 工作目录。以独立 Router Director Context 运行：

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

3. 启动**全新** PPT Master Context。只传递 `master_handoff` 中的原始材料路径、计划路径、用户明确模板／参考路径、简洁用户要求和短激活提示。不得把 Router conversation、Director Kernel、Profile、Lens、semantic vocabulary、scoring、capability map 或调试日志传入。
4. 新 Context 从 PPT Master 当前 `SKILL.md` 开始，按它实际命中的原生流程执行 Default Generate。`presentation_plan.md` 是已完成的专业内容与页面导演结果，原始材料仍是事实权威；不要重跑 Router 或创建第二份计划。

只有当 Master Stage 1 实质改变核心任务、材料范围或页面规模时，才停止当前 Master Context，重新启动独立 Router Context 更新计划，再启动新的 Master Context。普通确认不触发回流。

## Reference Implementation

`government_annual_summary` 是首个 Direct Plan Profile。它直接使用“页面任务、核心观点、内容关系、信息主次、表达意图、页面内容、可用素材、Speaker Notes”写计划，并给出成果数据、改革机制、下半年路径和问题建议的完整页面导演示例。

其他 Profile 保留现有专业知识，但尚未逐个升级为 reference 级别的完整页面导演 Prompt。

## 介入深度

- **FULL**：新生成或重构型专业汇报，包括政府年度／半年总结、政务专项汇报、经营分析、技术方案等。
- **LIGHT**：Quick、Beautify、需要先提炼内容的 Fill Native、明确专业场景的模板建设。
- **BYPASS**：Enhance Native、纯原生替换、纯模板提取、专业信号不足的模糊 PPT 请求。
