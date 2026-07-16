# PPT Director 3.1

PPT Director 以一个公开 `ppt-prompt-router` Skill 强集成固定版本的 PPT
Master runtime。Router负责场景、受众和导演约束；Master负责Strategist、
资源选择、SVG设计、机器检查、视觉复核和PPTX导出；Production State只负责
流程与Hash放行。

## 构建

```bash
python scripts/build_offline_suite.py sync-vendor --master-source <clean-master-clone>
python scripts/build_offline_suite.py build --output-dir <output-dir>
```

固定基线：

- Router `3567a510bd64e3197e009f5af4e02b03ac69af2c`
- PPT Master `f63de240cf25bd0fbbe384e5f344efa9a177726e`

离线包仅含一个公开Skill和根目录唯一`install.py`。目标机不需要Git或网络，
安装器不会修改plugin cache或marketplace，也不会联网安装Python依赖。

## 安装

```bash
python install.py install --host claude-code
python install.py validate --host claude-code
python install.py upgrade --host claude-code
python install.py rollback --host claude-code
python install.py uninstall --host claude-code --yes
```

存在任何宿主可发现的外部`ppt-master`或重复Router时返回`CONFLICT`；非受管
冲突只报告路径，不自动删除。安装完成后宿主只能发现一个相关Skill。

## 工作流

```text
start -> capability preflight -> mode-propose -> mode-select
-> Master模式化模板处理 -> plan -> lock-spec -> 样张 -> sample_confirmation
-> 用户A/B/C -> 逐页生产 -> midpoint review -> 全稿review -> export
```

`start`不做Plan、模板分析或设计规范。`template`和`premium`使用同一个总览页与
同一个复杂正文页生成A/B/C三组方向；三组内容输入相同，只允许Master改变设计。
`standard`继续使用原有三张风险样张流程。

项目产物始终位于Skill目录之外，日志只写入：

```text
<project>/logs/events.jsonl
<project>/logs/run_summary.md
```
