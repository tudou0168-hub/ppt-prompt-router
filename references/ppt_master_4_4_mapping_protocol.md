# Router Direct Plan → PPT Master 4.4+ 边界

`presentation_plan.md` 是 Router 与 PPT Master 的唯一主要业务接口。

- **Router Director**：读取原始材料和用户要求，选择专业 Profile，在独立上下文写入计划；不生成后续生产物。
- **PPT Master**：从自身 `SKILL.md` 与实际命中的原生流程开始，直接读取计划并结合原始事实、用户约束和 Stage 1 确认完成 Strategist、Design Spec / Lock、Executor、Review 与 Export。

计划使用自然语言栏目表达页面任务、核心观点、内容关系、信息主次、表达意图、页面内容、可用素材与 Speaker Notes。PPT Master 不需接收或机械翻译 Router 内部的六字段、Profile 或能力地图；它按自己的原生规则决定具体构图、Visual Style、Visualization、Native Shape、SVG 和其他条件能力。

权威顺序：用户明确约束与事实材料 → PPT Master 原生确认结果 → `presentation_plan.md`。若 Stage 1 实质改变核心任务、材料范围或页面规模，应以新的独立 Router 计划和新的 Master Context 恢复，而非在同一上下文往返切换技能。
