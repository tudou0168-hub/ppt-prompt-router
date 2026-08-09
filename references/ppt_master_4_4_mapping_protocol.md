# Router Direct Plan → PPT Master 4.4+ 边界

已迁移 Profile 的 `presentation_plan.md` 是 Router 与 PPT Master 的唯一主要业务接口；未迁移 Profile、LIGHT 和 BYPASS 没有该文件，直接交给 PPT Master 原生流程。

- **Router Director**：仅当 Profile 声明 `director_protocol: direct_plan_v1` 时，读取原始材料和用户要求，在独立上下文写入计划；不生成后续生产物。
- **PPT Master**：从自身 `SKILL.md` 与实际命中的原生流程开始，直接读取计划并结合原始事实、用户约束和 Stage 1 确认完成 Strategist、Design Spec / Lock、Executor、Review 与 Export。

计划使用自然语言栏目表达页面任务、核心观点、内容关系、信息主次、表达意图、页面内容、可用素材与 Speaker Notes。PPT Master 不需接收或机械翻译 Router 内部的六字段、Profile 或能力地图；它按自己的原生规则决定具体构图、Visual Style、Visualization、Native Shape、SVG 和其他条件能力。

Profile 输入权威顺序：用户明确要求 → 原始事实材料 → 用户明确模板／参考要求 → Profile 专业默认经验。Master 继续以其原生确认结果处理最终生产选择。若存在计划且 Stage 1 实质改变核心任务、材料范围或页面规模，应以新的独立 Router 计划和新的 Master Context 恢复，而非在同一上下文往返切换技能。
