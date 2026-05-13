# Runtime Architecture Rules

## CLI 与节点

- 运行时不是固定流程。
- 用户通过自然语言触发可选节点。
- 多节点串联前必须展示执行计划并获得确认。
- 缺少节点输入时，CLI 提示用户补齐。
- 节点之间只通过 SQLite session state 共享数据。
- 节点失败必须写入失败状态，不污染成功结果。

## 配置

- 配置文件路径固定为 `config/interview-agent.toml`。
- 不使用环境变量读取项目配置。
- LLM 和 embedding 配置都来自配置文件。
- 默认 embedding 模型为本地 `BAAI/bge-m3`。
- 对话、日志摘要和验证汇报中禁止输出、复述或暴露 key、token、密钥、证书、账号凭据及其他敏感信息。
- 验证 LLM 配置时只允许汇报是否存在、是否可用和错误类型，不展示敏感字段值。

## 知识库

- 知识库来源为 `/Users/cynicism/Desktop/面试`。
- 知识库必须在开发期离线预构建。
- `uv run interview-agent` 启动时只检查 ready 状态，不执行知识库接入。
- 知识库检索使用 SQLite FTS + 本地 bge-m3 embedding 混合检索。
- 不修改 `/Users/cynicism/Desktop/面试` 原始资料。
- 简历、离职证明、图片、Excel、公司流程类资料不得入库。
