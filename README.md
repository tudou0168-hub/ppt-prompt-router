# PPT Prompt Router 3.1.3 Stable

PPT Master 4.4+ 专业导演增强层。

核心偏好：

> **不考虑 Token、工具调用和思考次数，以最终汇报效果为优先，充分发挥 PPT Master 原生完整能力。**

## 本版关键变化

- 保持 **26 个** Director Profile，并修正政府阶段性总结与泛化政务汇报之间的优先级；
- 仅显式标记 `director_protocol: direct_plan_v1` 的 Profile 在独立 Director Context 写入 `presentation_plan.md`，结束后才启动全新 PPT Master Context；
- Router → Master 按 `material_paths`、可选计划路径、`template_paths`、`reference_paths`、`workspace_roots` 和用户明确约束做严格类型化交接；
- `government_annual_summary` 是首个直接生成自然语言页面导演稿的 reference implementation；
- PPT Master 直接读取计划并继续自行决定 Strategist、Visual Style、Visualization / Native Shape / SVG、Review 和 Export；
- FULL / LIGHT / BYPASS 均明确有无 Plan；未迁移 Profile、LIGHT 与 BYPASS 不传不存在的计划路径。Stage 1 只有实质改变核心任务、材料范围或页面规模时才重启独立 Router → Master 链路。

详细流程见 `SKILL.md`。
