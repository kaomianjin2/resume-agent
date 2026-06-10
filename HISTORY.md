# 功能变更历史

## 2026-06-10

### JOB-002 求职画像生成

- 功能名称：求职画像生成
- 测试命令：`rtk uv run pytest -p no:cacheprovider tests/test_gui_runtime.py`
- 测试结果：`32 passed in 0.43s`
- reviewer 结论：复审 `可继续`，无阻断问题。
- 影响范围：`src/interview_agent/gui_runtime.py`、`tests/test_gui_runtime.py`
- 变更摘要：新增 GUI Runtime 求职画像 facade，从已有 `resume_profile` 生成求职画像、默认搜索词、硬过滤条件、排序偏好和待确认字段；支持用户覆盖城市、远程、薪资、职级、经验、学历、行业、公司规模、融资阶段、技术栈、福利、发布时间、黑白名单，并把画像状态保存到 `session_state`。

### JOB-001 求职数据模型与存储设计

- 功能名称：求职数据模型与存储设计
- 测试命令：`rtk uv run pytest -p no:cacheprovider tests/test_storage.py`
- 测试结果：`14 passed in 0.12s`
- reviewer 结论：第三次复审 `可继续`，无阻断问题。
- 影响范围：`src/interview_agent/schema.sql`、`src/interview_agent/storage.py`、`tests/test_storage.py`
- 变更摘要：新增求职标准岗位、筛选条件、评估报告、确认批次、投递记录、采集任务和平台进度的 SQLite 持久化结构与存储 API；支持重复岗位识别、批次结果查询、平台进度查询、清空求职数据，并拦截明显敏感内容落库。
