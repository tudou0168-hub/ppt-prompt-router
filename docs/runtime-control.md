# 运行控制

跨宿主采用同一文件协议：

```text
Router 路由
→ 创建合同和导演 Profile
→ 当前主智能体读取 PPT Master 技能
→ 生成 Director Plan
→ 三张风险样张
→ 用户选择 A/B/C
→ 逐页生产
→ 中途检查
→ 全稿检查
→ 统一导出
```

Python 脚本不会直接启动另一个模型技能。不同模型可以产生不同构图，但受控项目必须满足样张、逐页、Hash、复核和导出门禁。

安装完成后，`install.py validate --host <host>` 会分别报告 Router、PPT Master overlay 和 runtime integration 三个状态；任一缺失或 Hash 不一致时，完整集成不视为安装成功。
