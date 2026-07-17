# 运行控制

跨宿主采用同一文件协议：

```text
Router 路由
→ 创建合同和导演 Profile
→ Content Strategist 提交并确认 Director Plan
→ Template Analyst（如需要）提交 Template Profile
→ Visual Director 提交 Design Genome
→ lock-spec 确定性编译 design_spec 与 spec_lock
→ 三个不同复杂设计探针并等待 Design Approval
→ 逐页生产
→ 中途检查
→ 全稿检查
→ 统一导出
```

Python 脚本不会直接启动另一个模型技能。不同模型可以产生不同构图，但受控项目必须满足三探针、逐页、Hash、复核和导出门禁。每个角色只保存一个覆盖式 Context，事件日志只保留 Context Hash。

安装完成后，`install.py validate --host <host>` 会分别报告 Router、PPT Master overlay 和 runtime integration 三个状态；任一缺失或 Hash 不一致时，完整集成不视为安装成功。
