# Router → PPT Master 调用链（3.1.3）

```text
原始材料 + 用户意图
        ↓
Router Preflight：场景语义、Profile、Lens、介入深度
        ↓ Stage 1（PPT Master 原生确认）
Router Director Handoff：Communication Contract + Profile + Lens + Director Kernel
        ↓
当前主智能体（专业 Director）实际写入 analysis/presentation_plan.md
        ↓
PPT Master Stage 2：读计划并形成 design_spec.md / spec_lock.md
        ↓
PPT Master Executor：SVG / Live Preview / Notes / PPTX / Postflight
```

边界保持明确：Router 不生成计划、不生产 SVG、不增加状态机或独立质量门禁。它只在 Stage 1 已确认后编译专业导演交接；计划、规格、锁定和最终页面是正常生产过程中的最小审计证据。

Stage 2 的输入规则：`relationship / hierarchy / rhythm_intent / visual_semantics` 决定逐页构图与关系结构；Visual Style 仅统一项目级视觉气质。卡片、dense 连续度和构图重复仅供人工审阅诊断，不设数量配额。

自动确认仅在名为 `router-regression` 的隔离项目中用于回归；安装后的 Router 与 PPT Master 正式流程仍保留原生用户确认。
