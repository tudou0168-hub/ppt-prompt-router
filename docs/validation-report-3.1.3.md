# PPT Prompt Router 3.1.3 Stable：验证报告

## 工程验证

- `python3 scripts/regression.py`：通过；26 个 Profile × 7 个中性变体与 6 个高风险案例，共 188 个路由用例，另含 4 条非默认路径及 Director handoff 校验。
- `python3 -m py_compile scripts/*.py installers/*.py`：通过。
- `python3 -m json.tool prompt-index.json`：通过。
- 临时安装目录执行 `install.py install` 与 `install.py validate`：通过。
- 政府半年总结冲突复现后验证：输入同时包含“政府汇报／管委会领导／上半年工作总结及下半年工作谋划”时，现稳定选择 `government_annual_summary`（阶段总结反证逻辑不会误伤建设方案）。

## 真实材料与产物

所有实测在 `/Users/muzi/Documents/ppt-master/skills/ppt-master/projects/router-regression-20260809` 下进行；原审批服务局旧项目未修改。

| 材料 | Router Profile | 已完成的代表性真实产物 |
| --- | --- | --- |
| 审批服务局半年总结 | `government_annual_summary` | 8 页完整 Router 代表样本：计划、规格、锁定、SVG、Live Preview、8 页 Notes、PPTX、Postflight、Contact Sheet |
| 五寨县“人工智能+”规划 | `government_strategy` | 体系关系代表页：计划、规格、锁定、SVG、Preview、Notes、PPTX、Postflight |
| 河南／郑州对标浙江差距分析 | `government_strategy` | 专网协同对照代表页：计划、规格、锁定、SVG、Preview、Notes、PPTX、Postflight |
| 智能招生经营提升方案 | `planning_proposal` | 12 周试点路线代表页：计划、规格、锁定、SVG、Preview、Notes、PPTX、Postflight |

后三份按用户的“只画复杂且容易卡片化的页面”指示，生产代表页而非为凑页数生成整册。三个代表页和审批服务局完整样本均通过最终 SVG 质量检查；PPTX 导出均生成 Postflight 通过报告。

## 三个核心问题的结论

1. **Profile 是否进入 Director：是。** 四个项目在 Director 阶段均返回 `ready` handoff；计划顶部写入 Router 版本、Primary Profile、Profile SHA-256 与 Stage 1 SHA-256。生成的 handoff 明确指令当前主智能体以匹配 Profile 实际写入 `presentation_plan.md`。
2. **计划是否改变 Stage 2／Executor：是。** 计划中的六字段直接映射到规格的 Layout、页面节奏和核心信息；最终页面分别采用数据证据、前后对比、服务系统、路线图、能力体系及治理路径对照，而不是由一个通用卡片版式覆盖。
3. **Router 是否提升导演与节奏：在已审阅的真实样本中是。** 审批服务局完整 Contact Sheet 呈现“数据证据→任务进展→改革对比→企业服务系统→下半年路线→保障”的结构转换；三份代表页分别保留系统、对照和时间关系。此结论限于已完成实测样本，不把路由用例数量当作视觉质量证明。

## 范围说明

本次没有修改 PPT Master 4.4 源码。审批服务局原生 A 基线作为只读失败基线保留；当前仓库没有从该基线生成可比较的原生 A 导出文件，因此本报告不把它表述为完成的同条件 A/B 成果。若需要正式 A/B 结论，下一步只需用同一材料补跑原生 Master A 的完整导出，并与本样本 Contact Sheet 做并排人工审阅。
