# 本轮审查交接：Direct Plan Handoff reference implementation

## 本轮目标

落实 Reviewer 对 `eb65124` 的确认：Router 在独立 Context 中直接完成 `presentation_plan.md`，再以严格路径式白名单启动全新的 PPT Master Context。只实现 `government_annual_summary` reference implementation，并用审批服务局 P03／P05／P06 完成 B2 因果实验。

## 修改内容

- `scripts/route.py`：移除“PPT Master Stage 1 → Router Director → 同一 Context Stage 2”的往返链、Stage 1 contract 入参及 Stage 2 semantic payload；Director 阶段仅准备普通 `<project>/analysis/` 并返回 Router-only director task。
- `scripts/route.py`：`master_handoff` 仅含原始材料路径、计划路径、用户明确模板／参考路径、简洁用户要求、短原生流程激活提示和 Stage 1 实质变更重启规则；不含 Router 内部上下文。
- `government_annual_summary`：改写为直接写入自然语言 `presentation_plan.md` 的专业导演 Prompt，包含成果数据、改革机制、行动路径、问题建议四个完整页面示例及反例。
- 同步更新 Router 运行说明、计划模板、Router→Master 边界说明和最小回归断言；未批量重写其余 25 个 Profile，未修改 PPT Master 源码。

## 测试

- `python3 scripts/regression.py`：通过，26 个 Profile、188 个路由案例、4 条非默认路径、Direct Plan handoff。
- `python3 -m py_compile scripts/route.py scripts/regression.py scripts/scoring.py scripts/semantics.py scripts/template_intent.py`：通过。
- 临时安装后 `python3 install.py validate --target <temp>`：通过。
- 手工 smoke：Director 阶段仅创建 `<project>/analysis/`；Master handoff 的序列化内容不包含 Director Kernel、Semantic Vocabulary、Primary/Secondary Profile、scoring 或 capability map。
- B2 隔离实测：独立 Router Context 先生成计划；独立 Master Context 从自己的 `SKILL.md` 运行 Default Generate，仅产出 P03／P05／P06。最终 SVG 3/3 通过，Visual Review 3/3 无问题，PPTX postflight `passed`、3 页、0 warning，ZIP 完整性通过。

## 关键证据

- B2 项目：`/Users/muzi/Documents/ppt-master/skills/ppt-master/projects/router-regression-20260809/approval-router-b2_ppt169_20260810`
- Router 正式产物：`analysis/presentation_plan.md`；该文件由独立 Router Context 直接写入，未带 Master 内容。
- B2 计划明确了 P03 的主数字／证据层级、P05 的机制—场景—成效边界、P06 的真实并列任务关系，未把并列六项任务伪造为路径。
- B2 最终 Contact Sheet：`.preview/contact_sheet.png`；最终 PPTX：`exports/approval-router-b2_20260810_070324.pptx`。
- 对照：A 原生 Contact Sheet 为 `approval-native-a-r1_ppt169_20260810/validation/contact_sheet_svg_rendered.png`；B1 旧 Router 为 `approval-router-b-r1_ppt169_20260809/validation/contact_sheet_svg_rendered.png`。

## 已知问题

- B2 是三页因果实验，不是新的八页完整成册结论；不能据此发布为 Stable 或推广到其余 25 个 Profile。
- P03 的主数字／环形证据结构有可见正增益；P05 的内容导演重心已从 B1 的“企业专区系统”改为“基层与群众服务”，因此不能把两张不同页面任务的视觉差异当作纯版式胜负。
- P06 明确把六项工作表达为真实并列战场，避免 B1 中无事实依据的连续路径；视觉上仍是稳健的六项信息分区，是否足以形成领导汇报的高级感仍需 Reviewer 人工判断。
- 当前机器缺少 Microsoft YaHei，LibreOffice 的最终 PPTX 渲染可能出现 CJK 字体替代；这属于本机字体／导出验证环境问题，不属于 Router。

## 请 Reviewer 重点判断

1. 严格路径式 `master_handoff` 是否已满足隔离边界，是否存在仍会把 Router 内部语义泄露给 Master 的字段或文档入口？
2. `government_annual_summary` 的自然语言计划格式是否已足以替代六字段作为正式业务接口，特别是“表达意图”能否真实指导页面视觉导演？
3. B2 P03 的明显层级改善，是否可以归因于新计划与 fresh Master context；P05/P06 的比较应如何避免把内容任务变化误判成视觉正增益？
4. 在只看到 P03/P05/P06 的情况下，下一步最小验证应是补齐同一八页 B2，还是先只修正新 Prompt 中 P05/P06 的页面任务与视觉导演具体度？请给出可证伪的判断标准。
