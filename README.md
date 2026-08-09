# PPT Prompt Router 3.1.3 Stable

PPT Master 4.4+ 专业导演增强层。

核心偏好：

> **不考虑 Token、工具调用和思考次数，以最终汇报效果为优先，充分发挥 PPT Master 原生完整能力。**

## 本版关键变化

- 保持 **26 个** Director Profile，并修正政府阶段性总结与泛化政务汇报之间的优先级；
- Default Generate 使用两阶段 Router 调用：Preflight 选 Profile，Stage 1确认后进入 Director phase；
- Director Payload 直接内联 Kernel + Semantic Vocabulary + Primary Profile + Lens；Router只编译 handoff，由当前主智能体作为专业 Director 生成计划；
- `presentation_plan.md` 写入 Router/Profile/Stage1 SHA 追踪头，交接是否发生可以直接审计；
- Stage 2 设计激活明确区分 Visual Style 与 Page Composition，并通过 relationship-driven recall 激活 Visualization / Native Shape / SVG / Visual Job Router 等 Master 原生能力；卡片和 dense 等只作审阅诊断，不设机械比例；
- workspace root 保留 `explicit_use_requested` 或 `candidate` 语义强度。

详细流程见 `SKILL.md`。
