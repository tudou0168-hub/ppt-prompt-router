# PPT Director 4.0 Phase 1

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

## Phase 1 工作流

```text
start -> mode-propose -> mode-select -> Content Strategist
-> Director Plan brief approval -> Template Analyst（需要模板时）
-> Visual Director Design Genome -> lock-spec机械编译
-> 三页正式设计探针 -> Design Approval -> 正式逐页生产
-> midpoint review -> 全稿review -> export
```

`start`不做Plan、模板分析或设计规范。三张不同复杂度设计探针直接走既有
`page-begin → page-check → render → review → page-pass`；三张均通过后只等待一次
Design Approval。`design_genome.json` 是唯一模型生成的设计事实源；`lock-spec`以
确定性模板编译 `design_spec.md` 和 `spec_lock.md`。Router 不生成逐页构图或视觉规范。

角色上下文按需写入 `.director/context/current/<role>.json` 并覆盖旧文件；事件日志只
记录其 Hash 和输入 Hash。验证快照写在项目外，不累计在正式项目中。

项目产物始终位于Skill目录之外，日志只写入：

```text
<project>/logs/events.jsonl
<project>/logs/run_summary.md
```
