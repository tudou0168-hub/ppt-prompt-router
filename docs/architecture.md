# 架构说明

PPT Prompt Router 是内容导演和场景路由入口，PPT Master 是页面生产底座。

```text
用户材料
→ Router 选择场景 Profile 与模板意图
→ director_contract.json 与 director_profile.md
→ PPT Master 生成唯一 director_plan.json
→ 生产状态控制样张、逐页检查、中途检查与全稿检查
→ 导出 PPTX
```

Router 不生成页面、不选择图表或布局、不保存页面状态。PPT Master 不重复选择场景 Profile。项目内只有一个导演规划和一个生产状态。

`reference_elements` 只继承参考模板的视觉语言；`native_fill` 保留原模板版式；`reusable_template` 创建可复用模板工作区；`none` 使用 PPT Master 默认流程。
