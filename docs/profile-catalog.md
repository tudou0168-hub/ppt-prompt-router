# 26 个专业 Director Profile

每个 Profile 的完整方法、叙事偏好与交接要求保存在 `prompt-index.json` 所指向的提示词文件中；Router 只选择并交接，不代替 Director 产出内容。

| Profile | 用途 |
| --- | --- |
| `work_report` | 工作汇报 |
| `planning_proposal` | 方案策划 |
| `product_introduction` | 产品介绍 |
| `business_bid` | 商务提案／投标 |
| `corporate_training` | 企业培训 |
| `meeting_speech` | 会议演讲 |
| `data_analysis` | 数据分析 |
| `classroom_lesson` | 课堂讲解 |
| `course_assignment` | 课程作业 |
| `thesis_defense` | 论文答辩 |
| `competition_pitch` | 竞赛路演 |
| `company_introduction` | 企业介绍 |
| `brand_presentation` | 品牌宣讲 |
| `franchise_recruitment` | 招商加盟 |
| `event_promotion` | 活动宣传 |
| `resume_profile` | 简历／个人介绍 |
| `fundraising_bp` | 融资 BP |
| `memorial_album` | 纪念相册 |
| `public_talk` | 公开课／公开演讲 |
| `government_annual_summary` | 政府年度／半年总结 |
| `government_strategy` | 政务汇报与战略规划 |
| `business_proposal` | 商务方案与客户提案 |
| `decision_meeting` | 决策会议与管理层拍板 |
| `data_report` | 数据报告与经营分析 |
| `teaching_explainer` | 教学解释与培训课件 |
| `product_technical` | 产品与技术方案 |

政府年度／半年总结在同时识别到政府域和阶段总结语义、且不存在“专项规划／建设方案／实施方案／战略规划／路线图”等反证时，优先选择 `government_annual_summary`；规划建设类仍走 `government_strategy`。
