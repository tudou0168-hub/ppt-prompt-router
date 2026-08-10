# 最小代表页测试协议

目标是验证 Router 程序能否稳定选择正确专业 Prompt、生成可用 `presentation_plan.md`，并通过最小路径激活 PPT Master。不是精修测试 PPT。

## 每轮规模

- 一次只测试 1 个 Profile / 1 类 PPT。
- 每类只从真实 `presentation_plan.md` 选择 3–4 张最有代表性的页面。
- 页码由真实材料决定，不固定 P01/P02/P03。

代表角色建议：

- `government_annual_summary`：成果证据 / 机制经验 / 下一步 / 问题建议。
- `government_strategy`：现状差距 / 总体体系或重点任务 / 实施路径 / 决策请示。
- `work_report`：关键结果 / 进度偏差或风险 / 下一步行动 / 资源协同。
- `decision_meeting`：决策问题 / 方案比较或权衡 / 推荐风险 / 拍板事项。
- `product_technical`：业务场景与能力 / 架构关系 / 流程或数据流 / 实施治理。

只选择材料真实存在的角色。

## Fail Fast

发现以下任一问题立即停止当前场景：

1. Router 选错 Profile；
2. 用户要求或输入路径丢失；
3. Plan 虚构事实、专业逻辑明显错误或过于空泛；
4. Stage 2 没有真实消费 Plan；
5. handoff/activation 导致 Master 跳过本任务应命中的原生流程；
6. 代表页出现可复现的硬故障，已经足以定位链路问题。

定位“第一处失真”：

- 路由/语义 → 修 Router scoring / semantics / registry；
- 专业判断 → 修对应 Profile；
- 路径、约束、上下文 → 修 handoff；
- Master 未正确启动 → 修 activation / 调用链；
- Plan 与 Spec 正确但 SVG/排版/素材锁定内部失败 → 记录 PPT Master 上游缺陷并停止；Router 不增加几何、字号、模板或页面特例补丁，也不修改 PPT Master 源码。

修复后从 Router 任务入口重新运行同一最小测试，不从失败中间状态续跑。

## 通过

3–4 张代表页足以确认：Profile正确、Plan专业、路径与约束正确、Master正常消费并发挥原生能力，即停止该场景，进入下一 Profile。不生成整套 PPT 作为程序验收前提。
