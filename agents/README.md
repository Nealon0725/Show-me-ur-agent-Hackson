# Agents

支持学校 LLM Gateway、OpenAI 与离线规则模式的简历证据评估工作流，不依赖第三方 Python 包。`llm_client.py` 统一 HTTP 调用，`model_provider.py` 负责提示词、结果映射和业务校验。

Gateway 配置：

| 环境变量 | 含义 |
| --- | --- |
| LLM_API_URL | 主办方提供的完整推理请求地址 |
| LLM_API_KEY | 服务端密钥 |
| LLM_MODEL | 主办方允许的模型名称 |
| LLM_API_STYLE | chat_completions（默认）或 responses |
| LLM_STRUCTURED_MODE | json_schema（默认）、json_object 或 prompt |
| LLM_TIMEOUT_SECONDS | 请求超时，默认 45 秒 |
| LLM_AUTH_HEADER | 认证 Header，默认 Authorization |
| LLM_AUTH_SCHEME | 认证前缀，默认 Bearer；无需前缀时设为 none |

`auto` 模式优先使用 LLM_API_KEY 对应的学校 Gateway，其次使用 OPENAI_API_KEY，最后使用规则。显式设置 `RECRUITMENT_AGENT_PROVIDER=gateway|openai|rules` 可以固定模式。协议不匹配或请求失败会返回 502，不会自动降级并改变评估标准。

`parse_jd(text)` 生成待人工确认的 criteria。`evaluate(text, criteria, answers=None)` 返回逐项结果，`Workflow` 控制确认、追问与人工决策。

评估 details 中保留原有字段并增加：

| 字段 | 含义 |
| --- | --- |
| description | 具体评估要求，前端确认标准时应展示 |
| context | financial 或 null；来自 JD 明确要求 |
| status | evidenced / not_met / unknown / needs_review（冲突） |
| reason | 判断解释，当前为英文规则模板 |
| evidence | 兼容原页面的证据文本列表 |
| evidence_refs | source、text、line；简历行号从 1 开始，补充回答 line 为 null |
| resume_evidence_refs | 采用人工补充判断时保留的简历原始证据 |

评估顶层的 model_usage 与 model_request_id 保存 Gateway 返回的调用信息（如有），但不保存 API Key。

顶层 unmet_requirements 列出明确不满足的技能；questions 仅追问信息不足或冲突项。覆盖率仅计算 evidenced 权重，不代替人工决策。明确不满足不会自动拒绝候选人。

JD 中的英文年限要求（例如 `1–2 years of relevant experience`）会生成 `type=experience` 标准，包含 minimum_years 和 target_years。相关经验单独逐项判断，`scored=false`，不混入技能覆盖率。job.human_review_items 固定列出学历/专业资格、薪资、工作资格和到岗时间，并保留 JD 中找到的原文；这些项目不自动评分。

规则仅支持有限英文句型。bare keyword、模糊自述不直接计分，但出现任务词也不保证自然语言判断正确。接入模型时应保留字段契约并扩大独立验收集。

验证：`python -B -m unittest discover -s tests -v`。
