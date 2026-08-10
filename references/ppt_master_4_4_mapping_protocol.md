# Router Direct Plan → PPT Master 4.4+ Mapping

`presentation_plan.md` 是 Direct Plan Profile 与 PPT Master 的主要业务接口。

页面导演结构映射：

- 页面总数、顺序、章节 → Content Outline / Page Roster
- 页面标题 → Title
- 页面任务 → Audience Move
- 核心观点 → Core Message
- 内容关系 + 信息主次 + 表达意图 → Layout / Page Rhythm / Visualization 的语义输入
- 页面内容 → Content
- 可用素材 → Images / Evidence
- Speaker Notes → Speaker Notes Requirements

Router 不输出具体坐标、固定版式、Native Shape 参数、SVG 参数或 Executor 几何。

PPT Master 结合原始材料、用户要求、模板/参考和 `presentation_plan.md`，自主完成当前版本的 Stage 1、Strategist / Stage 2、Design Spec / Lock、Executor、Review 与 Export。

Router → Master 交接只包含类型化路径、用户明确要求和短 activation，不传 Router 内部 Prompt 内容、Profile 全文、Lens、Kernel、scoring 或调试历史。
