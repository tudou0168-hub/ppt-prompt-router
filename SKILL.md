---
name: ppt-prompt-router
description: PPT 统一入口。确定性选择导演 Profile、识别模板意图、创建导演合同，并真实交接给 ppt-master。
version: 2.2.0
---

# ppt-prompt-router 2.2.0

本技能只负责路由与导演交接。它将通用导演协议与场景 Profile 编译为唯一的 `director_profile.md`；页面规划、设计、检查、修复和导出全部由 `ppt-master` 负责。

客户材料和项目产物只保留在本地项目中：不得把客户名称、客户文案、导出 PPTX、渲染 PNG、会话记录或个人绝对路径写入 Router 源码、测试和文档。

## 唯一入口

```bash
python3 <skill>/scripts/route.py \
  --request "<用户原始要求>" \
  --source <project_path>/source.docx \
  --template <template_path>/reference.pptx \
  --page-count <页数> \
  --audience "<受众>"
```

兼容入口 `python3 <skill>/install.py route ...` 必须委托给同一个 `route.py`。

## 固定动作

```text
接收任务
→ 确定性选择一个 Profile
→ 编译通用导演协议与场景 Profile
→ 识别模板意图
→ 创建 ppt-master 项目并导入材料
→ 写入 analysis/director_contract.json
→ 写入 analysis/director_profile.md
→ 调用 project_manager.py router-accept
→ 收到 accepted=true 后结束 Router
```

不得把 Profile 写入 `sources/`，不得生成 Storyline、页面规划或生产状态的副本。

## 路由规则

- 用户指定 `prompt_id`：直接选择。
- `required_signals`：每项 `+6`。
- `strong_signals`：每项 `+3`。
- `supporting_signals`：每项 `+1`。
- `negative_signals`：每项 `-5`。
- `avoid_when`：每项 `-8`。
- 匹配用户请求、受众、目的、文件名，以及必要的材料标题和开头。
- 最高分低于 `3`，或前两名分差小于 `2`：只询问一次场景。

`government_strategy` 是已验证 Profile；其他 Profile 默认实验性。

## 模板意图

- `reference_elements`：只提炼设计语言，重新设计页面。
- `native_fill`：保留原模板版式并填充内容。
- `reusable_template`：提炼为可复用模板工作区。
- `none`：进入 PPT Master 默认设计流程。

用户提供 PPTX 但意图不明确时，只询问模板用途。

## 验收

- `director_contract.json` 只保存版本、Profile、受众、目的、页数、模板路径和模板意图。
- `director_profile.md` 的 SHA256 必须与合同一致。
- 六个重点 Profile 必须具备完整场景字段；其余 Profile 使用公共默认值并保持实验性。
- `router-accept` 必须真实返回 `accepted=true`。
- Router 不得以“正在调用”代替机器交接。
- 后续唯一导演规划是 `analysis/director_plan.json`，唯一生产状态是 `analysis/production_state.json`。
