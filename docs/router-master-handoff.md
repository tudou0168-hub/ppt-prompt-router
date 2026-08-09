# Router → PPT Master 调用链（Direct Plan Handoff）

```text
原始材料 + 用户明确要求
        ↓
Router Preflight：选择 Profile 和 execution_path
        ↓
Direct Plan Profile：独立 Router Context 写入计划；其他模式：无 Plan
        ↓
全新 PPT Master Context：只接收路径白名单与短激活提示
        ↓
PPT Master 原生 Default Generate：Stage 1 → Stage 2 → Spec/Lock → Executor → Review/Export
```

Router 只负责普通工作目录下 `analysis/` 的准备和计划写入；仅已登记 `director_protocol: direct_plan_v1` 的 Profile 走这条链。不拥有项目初始化、Master bootstrap 或额外状态协议。

传给全新 PPT Master Context 的内容只有：`material_paths`、可选 `presentation_plan_path`、`template_paths`、`reference_paths`、`workspace_roots`、原始用户任务、audience、page count、format、delivery purpose、用户明确章节／标题／图片／事实／模板约束，以及一段激活其当前 `SKILL.md` 和原生流程的短提示。PPT Master 直接读取存在的计划，不接收 Router 的 Profile、Lens、Kernel、词汇表、评分、能力地图、调试日志或第二层语义转译。

如 Master Stage 1 实质改变核心任务、材料范围或页面规模，停止该 Master Context；在新的独立 Router Context 更新计划后，重新启动新的 Master Context。日常 Stage 1 确认不触发回流。
