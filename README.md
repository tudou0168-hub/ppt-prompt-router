# PPT Prompt Router 3.1.3 Stable

PPT Master 4.4+ 专业导演增强层。

核心偏好：

> **不考虑 Token、工具调用和思考次数，以最终汇报效果为优先，充分发挥 PPT Master 原生完整能力。**

## 本版关键变化

- 保持 **26 个** Director Profile，并修正政府阶段性总结与泛化政务汇报之间的优先级；
- Router 在独立 Director Context 直接写入 `presentation_plan.md`，结束后才启动全新 PPT Master Context；
- Router → Master 只交接原始材料路径、计划路径、用户明确的模板／参考路径、简洁任务和短原生流程激活提示；
- `government_annual_summary` 是首个直接生成自然语言页面导演稿的 reference implementation；
- PPT Master 直接读取计划并继续自行决定 Strategist、Visual Style、Visualization / Native Shape / SVG、Review 和 Export；
- Stage 1 只有实质改变核心任务、材料范围或页面规模时才重启独立 Router → Master 链路。

详细流程见 `SKILL.md`。
