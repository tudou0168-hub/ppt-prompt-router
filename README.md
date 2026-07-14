# PPT Prompt Router 2.1

PPT Prompt Router 是 `ppt-master` 的统一导演入口：确定性选择场景 Profile、识别模板用途、将通用导演协议与场景差异编译为唯一导演 Profile，并通过机器握手真实启动 PPT Master。

```text
一个入口 route.py
一个导演合同 director_contract.json
一个导演规划 director_plan.json
一个生产状态 production_state.json
一条逐页闭环
```

## 使用

```bash
python3 scripts/route.py \
  --request "参考模板设计元素，根据材料设计15页政府领导汇报PPT，不要套版" \
  --source <project_path>/source.docx \
  --template <template_path>/reference.pptx \
  --page-count 15 \
  --audience "政府领导"
```

模板意图可显式指定：

```bash
--template-intent reference_elements
--template-intent native_fill
--template-intent reusable_template
--template-intent none
```

兼容命令 `python3 install.py route ...` 委托给同一个入口。

## 安装与验证

```bash
python3 install.py detect
python3 install.py install --host codex --master-root <ppt_master_root>
python3 install.py validate --host codex --master-root <ppt_master_root>
python3 install.py uninstall --host codex --master-root <ppt_master_root> --yes
```

安装器安装 Router，并只对标准 PPT Master 应用清单声明的最小覆盖层。上游 Hash 不匹配会停止，失败时自动恢复。运行要求为 Python 3.10 或更高版本。

## 产品边界

- Router 只路由和交接，不生成页面。
- Router 决定受众、沟通目标、语体、叙事节点、事实边界和关键退化风险；不选择页面资源、布局或 SVG 实现。
- Profile 快照只进入 `analysis/`，不进入 `sources/`。
- `government_strategy` 为已验证 Profile，其他 Profile 默认实验性。
- 页面生产、样张确认、中途检查、全稿检查和导出预检由 PPT Master 的生产控制内核负责。
- 客户材料、项目产物、渲染图片、PPTX、DOCX、PDF、缓存和本机路径不得进入仓库。
