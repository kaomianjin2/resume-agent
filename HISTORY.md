# 功能变更历史

## 2026-06-10

### JOB-001 求职数据模型与存储设计

- 功能名称：求职数据模型与存储设计
- 测试命令：`rtk uv run pytest -p no:cacheprovider tests/test_storage.py`
- 测试结果：`14 passed in 0.12s`
- reviewer 结论：第三次复审 `可继续`，无阻断问题。
- 影响范围：`src/interview_agent/schema.sql`、`src/interview_agent/storage.py`、`tests/test_storage.py`
- 变更摘要：新增求职标准岗位、筛选条件、评估报告、确认批次、投递记录、采集任务和平台进度的 SQLite 持久化结构与存储 API；支持重复岗位识别、批次结果查询、平台进度查询、清空求职数据，并拦截明显敏感内容落库。
