# 已废弃：三人开发分工

团队现已确认为四人，其中两人共同负责 Agent。Agent 分工请使用 `docs/agent-pair-workplan.md`。

## 共同目标

输入一份 JD 和多份简历，系统按照招聘者确认的同一套标准进行证据评估、解释、追问和排序。Agent 只给建议，最终入围、拒绝和对外沟通必须由招聘者确认。

```text
Frontend ──► Backend / Database ──► Agent ──► School LLM Gateway
   ▲                 │                 │
   └──── 展示结果 ◄──┴──── 结构化结果 ─┘
```

## 负责人 A：Agent（你）

负责系统如何理解和判断。

文件范围：

- `agents/`
- `tests/test_screening.py`
- `tests/test_model_provider.py`
- `tests/test_llm_client.py`
- `tests/test_workflow.py`
- Agent ground truth 数据

任务：

1. JD 结构化解析。
2. 简历证据提取、引用和逐项判断。
3. documented score、possible score、evidence completeness 和排名。
4. `SHORTLIST / REQUEST_INFO / HUMAN_REVIEW / LOW_MATCH` 建议动作。
5. 补充回答后的重新评估。
6. 学校 LLM Gateway 接入、异常处理和用量记录。
7. PII/sensitive attributes 不进入评分。
8. Agent 单元测试和人工标准答案。

Agent 接收纯文本和来源位置，返回结构化 JSON；不直接操作页面和数据库。

## 负责人 B：Frontend

负责招聘者看到和操作的页面。

文件范围：

- `frontend/`
- 前端测试和静态资源

任务：

1. JD 输入及 5–10 份简历的多文件选择。
2. 显示上传、解析和评估进度，以及单个文件错误。
3. 岗位标准确认页面。
4. 候选人列表和排序页面。
5. 展示三个分数、建议动作、优势、缺口和待确认信息。
6. 展示每条要求的 reason 和 evidence_refs（文件、页码/行号、原文）。
7. 追问回答录入与重新评估页面。
8. 人工 shortlist、hold、decline 和必填理由输入。
9. 刷新后根据 run ID 恢复页面。

Frontend 只调用 Backend API，不直接调用 LLM，也不保存 API Key。

## 负责人 C：Backend / Database / Deployment

负责文件进入系统、API、持久化和运行环境。

文件范围：

- `backend/`
- `tools/store.py`
- `tools/resume_reader.py`（待创建）
- `tests/test_api.py`
- 数据库迁移和 Lightsail 部署配置

任务：

1. 接收 JD 和多份 PDF/DOCX 文件。
2. 将文件转换成纯文本，并保留文件名、页码或段落位置。
3. 调用 Agent 的固定 Python 接口。
4. 实现和维护 runs、confirm、followup、review 等 API。
5. 保存岗位标准版本、候选人、评估、追问、人工决定和事件日志。
6. 页面刷新后恢复完整 run 状态。
7. 验证文件类型、大小和空文件，返回清晰错误。
8. API Key 只使用服务端环境变量，不写数据库和日志。
9. 配置 AWS Lightsail 启动、重启、日志和健康检查。
10. 后续支持数据删除和保留期限。

Backend 不修改 Agent 的评分公式和提示词；Database 不需要解析模型输出含义，只按合同保存字段。

## 三方接口合同

### Frontend → Backend

```json
{
  "jd": "raw job description",
  "resume_files": ["candidate-a.pdf", "candidate-b.docx"]
}
```

### Backend → Agent

```json
{
  "job": {"criteria_version": 1, "criteria": []},
  "candidate": {
    "id": "C001",
    "document_name": "candidate-a.pdf",
    "text": "...",
    "source_segments": [
      {"page": 1, "line": 4, "text": "Used Xero for reconciliation."}
    ]
  },
  "followup_answers": {}
}
```

### Agent → Backend → Frontend

```json
{
  "candidate_id": "C001",
  "criteria_version": 1,
  "documented_score": 78,
  "possible_score": 100,
  "evidence_completeness": 78,
  "details": [],
  "strengths": [],
  "gaps": [],
  "missing_information": [],
  "questions": [],
  "recommendation": "Potential match; clarification recommended.",
  "action": "REQUEST_INFO",
  "model_usage": {},
  "model_request_id": null
}
```

四种 action 都是流程建议，不是最终招聘决定。

## Git 分支

```text
你：       feature/resume-agent-v2
Frontend：feature/frontend
Database：feature/backend-storage
```

三人不要直接提交到 `main`。通过 Pull Request 合并；共享接口发生变化时，先更新示例 JSON 和测试，再通知另外两人。

## 可以立即并行开始的工作

- Agent：实现分数区间、四种 action 和排序。
- Frontend：使用固定示例 JSON 完成标准确认、候选人列表和证据展示。
- Backend/Database：完成 PDF/DOCX 读取、文件 API、状态保存和 Lightsail 配置。

第一轮联调使用 `data/demo.json`。C001 应进入人工入围审核；C002 应因 Xero 缺失进入 REQUEST_INFO；C003 应显示 Xero 明确不满足以及其他信息不足。最终决定必须要求人工填写理由。
