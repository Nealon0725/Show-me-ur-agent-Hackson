# 两人开发分工：Singapore SME Resume Screening Agent

## 1. 产品目标

输入一份职位描述和多份简历，系统按招聘者确认的同一套标准整理每位候选人的相关证据、缺口和待确认信息，给出可解释的排序与下一步建议。Agent 不直接录用或拒绝候选人；最终入围、拒绝和外部沟通必须由招聘者批准。

第一版只面向 Accounts Executive，并使用虚构或已匿名化数据。

## 2. 系统边界

```text
浏览器
  │  JD、简历文件、人工确认、补充回答、最终决定
  ▼
Backend API ───────────────► SQLite / 文件存储
  │                         岗位、候选人、评估、事件
  │  纯文本 + 来源位置
  ▼
Recruitment Workflow
  │
  ├── JD Parser
  ├── Resume Evidence Evaluator
  ├── Scoring / Ranking
  ├── Next-action Policy
  └── LLM Client ──────────► 学校 LLM Gateway
```

双方最重要的边界：平台层负责把文件可靠地转换为带来源位置的文本；Agent 层只接收文本和结构化标准，不直接处理页面、数据库连接或用户文件。

## 3. 人员 A：Agent 与评估逻辑（你）

负责“系统如何理解和判断”。

文件所有权：

- `agents/llm_client.py`
- `agents/model_provider.py`
- `agents/parsers.py`，后续可拆成 `jd_parser.py` 和 `resume_parser.py`
- `agents/screening.py`
- `agents/workflow.py`
- `agents/schemas.py`（待创建）
- `agents/prompts.py`（待创建）
- `tests/test_llm_client.py`
- `tests/test_model_provider.py`
- `tests/test_screening.py`
- `tests/test_workflow.py`
- `data/ground_truth/`（待创建）

主要任务：

1. 将学校 Gateway 接入统一 LLM 客户端。
2. 从 JD 提取必需、优先、经验和人工核实标准，并要求招聘者确认。
3. 从简历逐项提取证据，输出状态、理由和原文引用。
4. 实现 `evidenced / not_met / unknown / needs_review` 四种证据状态。
5. 实现 documented score、possible score 和 evidence completeness。
6. 实现候选人排序，但不把待澄清候选人直接当作低匹配。
7. 实现 `SHORTLIST / REQUEST_INFO / HUMAN_REVIEW / LOW_MATCH` 四种建议动作。
8. 生成追问，并在收到补充回答后只重新评估受影响的标准。
9. 防止简历中的指令改变评估标准；不使用敏感个人属性评分。
10. 用人工标注样例评估证据准确性、动作正确性和稳定性。

完成标准：所有结论都有可核对的原文；缺失信息不会被直接当成不满足；模型输出异常会明确失败；规则、Gateway 和 OpenAI 备用模式共享同一份结果格式。

## 4. 人员 B：前端、文件、数据库与部署（朋友）

负责“招聘者如何使用系统，以及数据如何可靠保存”。Agent 的评分和推荐规则由人员 A 提供，人员 B 不需要编写模型提示词或判断逻辑。

文件所有权：

- `frontend/`
- `backend/`
- `tools/store.py`
- `tools/resume_reader.py`（待创建）
- `tests/test_api.py`
- Lightsail 部署文件和运行脚本

### P0：Demo 必须完成

1. **JD 和多份简历输入**
   - 支持粘贴 JD。
   - 支持一次选择 5–10 份简历。
   - 显示文件名、处理进度和失败原因。

2. **PDF/DOCX 转文本**
   - 输出正文及页码或段落位置。
   - 解析失败不能返回空文本冒充成功。
   - 不修改原文内容；PII 清理由 Agent 前的独立步骤处理。

3. **岗位标准确认页**
   - 展示必需、优先、最低经验和人工核实项目。
   - 招聘者确认后才开始批量筛选。
   - 标准有误时允许修改 JD 并创建新评估。

4. **候选人结果页**
   - 展示三个分数、建议动作、优势、缺口和待确认信息。
   - 每条判断显示原文证据及页码/行号。
   - 展示候选人排序，同时标出 `REQUEST_INFO` 和 `HUMAN_REVIEW`。

5. **补充信息与人工决定**
   - 招聘者可以录入候选人回答并触发重新评估。
   - 保存 shortlist、hold、decline 和必填理由。
   - 不自动发送邮件。

6. **状态与数据库**
   - 保存岗位标准版本、候选人、评估结果、补充回答和事件日志。
   - 页面刷新后能恢复评估。
   - API Key 只存在服务端环境变量中，不进入数据库、页面或日志。

7. **Lightsail 部署**
   - 提供启动命令和环境变量说明。
   - 服务异常后能够重启。
   - 设置请求大小限制，不公开 SQLite 文件和上传目录。

### P1：Demo 稳定后再做

- 招聘者登录及角色权限。
- 删除候选人数据和数据保留期限。
- 批量筛选进度、失败重试和取消任务。
- CSV 导出和审计日志页面。
- 更完整的移动端布局和无障碍支持。

## 5. 双方共同遵守的数据契约

人员 A 定义字段语义，人员 B 负责保存和展示。任何字段改名或状态含义变化，需要双方确认。

### Agent 输入

```json
{
  "job": {
    "id": "J001",
    "criteria_version": 1,
    "criteria": []
  },
  "candidate": {
    "id": "C001",
    "document_name": "candidate-001.pdf",
    "text": "...",
    "source_segments": [
      {"page": 1, "line": 4, "text": "Used Xero for monthly reconciliation."}
    ]
  },
  "followup_answers": {}
}
```

### Agent 输出

```json
{
  "candidate_id": "C001",
  "criteria_version": 1,
  "documented_score": 78,
  "possible_score": 100,
  "evidence_completeness": 78,
  "details": [
    {
      "criterion_id": "xero",
      "status": "unknown",
      "reason": "The resume does not identify the accounting software used.",
      "evidence_refs": []
    }
  ],
  "strengths": [],
  "gaps": [],
  "missing_information": ["Xero experience"],
  "questions": [],
  "recommendation": "Potential match; clarification recommended.",
  "action": "REQUEST_INFO",
  "model_usage": {},
  "model_request_id": null
}
```

### 动作含义

| 动作 | 含义 | 人工控制 |
| --- | --- | --- |
| SHORTLIST | 建议进入人工入围审核 | 招聘者确认后才正式入围 |
| REQUEST_INFO | 关键证据缺失 | 招聘者审核追问并记录回答 |
| HUMAN_REVIEW | 证据冲突、低置信度或规则无法覆盖 | 招聘者判断 |
| LOW_MATCH | 已确认的岗位相关证据较弱 | 招聘者批准后才可拒绝 |

## 6. 协作规则

1. 两人各自使用独立 Git 分支，避免同时修改同一文件。
2. 人员 A 不直接更改数据库结构和主要页面；人员 B 不直接修改评分公式、提示词和动作规则。
3. `agents/schemas.py`、`agents/workflow.py`、API 路由及响应示例属于共享接口，修改前先同步。
4. 数据库保存 `criteria_version`。岗位标准改变后创建新版本，旧评估保持可追溯。
5. 使用固定的虚构样例做集成测试，禁止把真实简历提交到 Git。
6. API Key 写入 Lightsail 环境变量，不写入 `.env` 示例值、前端或提交记录。

## 7. 两周内的推荐顺序

| 阶段 | 人员 A | 人员 B | 集成验收 |
| --- | --- | --- | --- |
| 1. 固定接口 | schemas、分数和动作定义 | API/数据库字段映射 | 三份 JSON 样例可保存和展示 |
| 2. 完成核心 | 排名、PII 清理、Gateway 适配 | 文件上传、PDF/DOCX 解析 | 一份 JD + 三份文件跑通 |
| 3. 完成闭环 | 追问重评、用量记录 | 追问页面、事件记录 | B 缺 Xero 后补充并重评 |
| 4. Demo 加固 | Ground truth 和异常测试 | Lightsail、错误提示、恢复 | 5–10 份简历稳定演示 |

## 8. 给朋友的当前开工清单

朋友现在可以在不等待 Agent 后续开发的情况下完成：

1. 创建 `tools/resume_reader.py`，把 PDF/DOCX 输出为带页码或段落位置的文本。
2. 在前端加入多文件选择、文件列表、进度和失败提示。
3. 让后端接受文件并调用 resume reader，但传给 Agent 的最终输入仍为纯文本与来源位置。
4. 在结果表中加入 reason、evidence_refs、human_review_items 和 model_usage 的展示位置。
5. 保持现有 `/api/runs`、`/confirm`、`/followup`、`/review` 流程兼容。
6. 准备 Lightsail 启动脚本和环境变量配置说明。

第一轮联调标准：使用 `data/demo.json`，C001 进入人工入围审核，C002 因 Xero 缺失进入 REQUEST_INFO，C003 显示明确缺少 Xero 经验和其余信息不足；任何最终决定都需要人工填写理由。
