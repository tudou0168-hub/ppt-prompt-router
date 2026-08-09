# 本轮审查交接：程序级 Direct Plan 兼容与路径协议

## 本轮目标

将研发焦点从审批服务局样本页转回 PPT Prompt Router 程序：确保 Router 能依据真实专业场景选择 Profile；仅由已迁移 Profile 在独立 Context 生成计划；并以严格、类型化的路径交接启动 fresh PPT Master Context。

## 修改内容

- `prompt-index.json`：只为 `government_annual_summary` 标注 `director_protocol: direct_plan_v1`；其余 25 个旧 Profile 不被强行套入新协议。
- `scripts/route.py`：新增显式 `execution_path`。只有 `FULL + direct_plan_v1` 走 `router_director_then_fresh_master`；FULL 未迁移、LIGHT 与 BYPASS 都走 `fresh_master_without_plan`，不传不存在的计划路径。
- `scripts/route.py`：`master_handoff` 改为严格类型化路径：`material_paths`、可选 `presentation_plan_path`、`template_paths`、`reference_paths`、`workspace_roots`。Router 内部 Prompt、Profile、Lens、scoring、词汇、能力地图和调试过程仍不跨越该边界。
- `scripts/route.py`：保留原始用户任务、audience、page count、format、delivery purpose 及显式章节／标题／图片／事实／模板／其他约束；Director Prompt 明确执行“用户明确要求 → 原始事实材料 → 用户明确模板／参考要求 → Profile 默认经验”的优先级。
- `government_annual_summary`：修正默认判断式标题和叙事只能在用户未指定时使用，不能覆盖用户的标题、章节、页数或素材策略。

## 测试

- `python3 scripts/regression.py`：通过，26 个 Profile、188 个路由案例、4 条非默认路径；额外断言 Direct Plan 迁移资格、FULL/LIGHT/BYPASS 有无 Plan、Master typed paths、用户约束保留和旧 Profile 禁止 Director phase。
- `python3 -m py_compile scripts/route.py scripts/regression.py scripts/scoring.py scripts/semantics.py scripts/template_intent.py`：通过。
- `python3 -m json.tool prompt-index.json`：通过。
- 临时安装后 `python3 install.py validate --target <temp>`：通过。

## 关键证据

- 迁移 Profile 输出：`execution_path.requires_presentation_plan=true`、`director_protocol=direct_plan_v1`，且仅这时 handoff 含 `presentation_plan_path`。
- 未迁移 `government_strategy` 仍可被正确选择，但输出 `director_task.status=not_migrated` 与无 Plan 的 fresh Master 路径。
- Master handoff 只含输入路径和用户明确约束；回归对序列化 handoff 检查了 Router 内部字段不得泄露。

## 已知问题

- 当前只有一个 Direct Plan Profile；这符合本轮“按 Profile 显式迁移”的范围，不代表其余场景已经具备专业 Director 能力。
- 本轮没有生成或精修审批服务局 B2.1，也没有把一次 PPT 样本表现当成程序通过标准。
- 多场景真实盲测尚未开始；必须在 Reviewer 确认协议边界后执行，且不得基于第一轮的单页布局问题立刻改 Profile 再声称验证通过。

## 请 Reviewer 重点判断

1. `director_protocol: direct_plan_v1` 的 Profile 级兼容策略是否足够轻，是否还需要任何额外状态或迁移机制？
2. FULL 未迁移、LIGHT、BYPASS 的无 Plan fresh Master 路径，是否与 Router/PPT Master 的职责边界一致？
3. typed path handoff 与用户约束字段是否遗漏了会影响真实任务的输入类型，或存在不应跨 Context 的字段？
4. 建议的盲测集是否足以先检验程序问题：政府年度／半年总结、政府专项规划／建设方案、企业经营总结／复盘、技术解决方案、决策汇报、已有 PPT 美化、Native 增强、专业信号不足的普通 PPT。
