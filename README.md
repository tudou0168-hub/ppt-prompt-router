# PPT Prompt Router 3.1.3

PPT Prompt Router 是 PPT Master 4.4+ 的专业导演增强层，不是第二套 PPT 生成系统。

生产链：

```text
用户材料/模板/参考/要求
        ↓
Router Preflight：选择专业 Profile
        ↓
Direct Plan Profile：独立 Context 读取路径并生成 presentation_plan.md
        ↓  Router Context 结束
fresh PPT Master Context
        ↓
只接收材料/Plan/模板/参考路径 + 用户要求 + 短 activation
        ↓
PPT Master 当前原生完整流程
```

当前 Direct Plan Profile：

- government_annual_summary
- government_strategy
- work_report
- decision_meeting
- product_technical

核心边界：

- Router 决定“用哪种专业导演方法、讲什么、关系和主次是什么”。
- PPT Master 决定“怎么设计、怎么画、怎么生产和怎么导出”。
- Router → Master 只传类型化路径与用户要求，不传 Router 内部上下文。

测试原则见 `TESTING.md`：一类 PPT 每轮只生产 3–4 张代表页，发现第一处硬问题立即停止、定位根因、修程序并从 Router 入口重跑。
