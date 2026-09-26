# Singapore SME Recruitment Assistant

最小可运行的招聘流程演示。Python 3.10+，仅标准库；离线规则模式无需 API Key。

## Agent B 整合更新（2026-09-26）

- 已接入三个指标：已有证据覆盖率、可能覆盖率、证据完整度。
- 已接入 SHORTLIST、REQUEST_INFO、HUMAN_REVIEW、LOW_MATCH 四种建议。冲突优先交人工复核，必需项明确不满足则 LOW_MATCH，必需项缺信息则追问，最多两轮。
- 页面按动作、分数、完整度和候选人 ID 稳定排序，展示判断理由和证据行号。API 保留原始候选人数组顺序，通过 rank 表示排名。
- provisional 表示仍存在追问或人工复核建议；final 仅代表当前规则排序，不是录用结果。人工决定不会将候选人移到排名末尾。
- 补充回答复用已保存证据，只覆盖回答涉及的项目，再重新算分、判断动作和排名，不重复调用模型。
- 旧记录读取时基于已保存证据补齐新字段，更新时保存。保留 score、unmet_requirements 和事件 detail 兼容字段。
- 新建评估包含 criteria_version=1；修改 JD 仍需新建评估。人工决定只允许在 SHORTLIST_REVIEW、LOW_MATCH_REVIEW、HUMAN_REVIEW 状态提交，理由必填。
- PDF/DOCX 读取、PII 屏蔽、学校 Gateway 真实联调和多人部署仍待完成。

## 启动

在仓库根目录运行：

```sh
python -m backend.server
```

默认采用 `auto` 模式，优先顺序为学校 LLM Gateway、OpenAI、离线规则。学校提供 Gateway 后使用：

```powershell
$env:LLM_API_URL = "主办方提供的完整请求地址"
$env:LLM_API_KEY = "主办方提供的 API Key"
$env:LLM_MODEL = "主办方提供的模型名称"
$env:RECRUITMENT_AGENT_PROVIDER = "gateway"
python -m backend.server
```

默认假设 Gateway 兼容 OpenAI Chat Completions 和 JSON Schema。拿到主办方请求示例后，可按实际情况设置：

```powershell
$env:LLM_API_STYLE = "chat_completions"  # 或 responses
$env:LLM_STRUCTURED_MODE = "json_schema" # 或 json_object / prompt
```

OpenAI 仍作为开发备用方案：

```powershell
$env:OPENAI_API_KEY = "你的 API Key"
$env:RECRUITMENT_AGENT_PROVIDER = "openai"
$env:OPENAI_MODEL = "gpt-5.6-luna"
python -m backend.server
```

API Key 只放在服务进程环境变量中，不要提交到仓库、写入前端或发送给浏览器。可设置 `RECRUITMENT_AGENT_PROVIDER=rules` 强制使用离线规则。模型结论经过服务端字段完整性、状态值和证据行号校验，失败时返回 502，不会静默切换评估标准。每次评估保存 Gateway 返回的 usage 和 request ID（如有），方便统计成本与排错。

浏览器打开 http://127.0.0.1:8000 。可通过 `--port 8001` 更换端口。

```sh
python -m unittest discover -s tests -v
```

## 三分钟 Demo

1. 点击「载入示例」，再点击「解析 JD，创建评估」。示例均为虚构数据。
2. 审核提取出的必需 / 优先技能，再确认开始评估。
3. C001 显示 SHORTLIST 建议，等待人工审核；C002 缺少 Xero 信息，显示 REQUEST_INFO 和追问；C003 显示 LOW_MATCH，仍需人工审核。
4. 给 C002 的 Xero 问题填写 `I used Xero for invoice reconciliation for one year.`，选择「回答提供了相关证据」，记录回答。
5. C002 的技能证据覆盖率从 78 提升到 100，进入人工审核。选择人工批准入围并填写理由。
6. 查看 Agent 行动记录：SCREEN → REQUEST_INFO → FOLLOWUP_RECORDED → RE_EVALUATE → SHORTLIST → HUMAN_DECISION。

## 架构与分工接口

| 目录 | 内容 |
| --- | --- |
| agents/parsers.py | JD 和简历纯文本解析 |
| agents/screening.py | 逐项证据、技能覆盖率、缺失信息和追问 |
| agents/workflow.py | 状态流转、两轮上限、重新评估与人工决策 |
| agents/llm_client.py | 学校 Gateway / OpenAI 的可替换 HTTP 客户端 |
| agents/model_provider.py | 将模型结构化输出映射并校验为简历证据 |
| tools/store.py | SQLite 本地持久化 |
| backend/server.py | 本地 HTTP API |
| data/demo.json | 三份虚构简历与新加坡 SME Accounts Executive JD |
| frontend/index.html | 无构建依赖的演示页面，可由 UI 同学替换 |

原仓库仅有 README 和 test.py；保留原 test.py，新增上述模块。

API（JSON）：

- `GET /api/demo`：示例输入。
- `POST /api/runs`：`{"jd":"...", "resumes":["..."]}`，解析 JD，等待人工确认。
- `GET /api/runs/{id}`：恢复完整状态。
- `POST /api/runs/{id}/confirm`：`{}`，确认标准并筛选。
- `POST /api/runs/{id}/followup`：`{"candidate_id":"C002", "answers":{"xero":{"status":"evidenced", "evidence":"Used Xero for invoicing."}}}`。状态可为 evidenced、not_met、unknown；只接受当前待澄清项。
- `POST /api/runs/{id}/review`：`{"candidate_id":"C002", "decision":"shortlist", "reason":"Reviewed evidence."}`。人工可选择 shortlist、hold、decline。

## MVP 边界

这是支持 **GPT 与离线规则双模式** 的 Agent 工作流原型。岗位 JD 仍由有限英文词表规则解析；简历证据可由 GPT 理解，也可使用离线规则。必需技能权重 2，优先技能权重 1。证据判断分为 evidenced、not_met、unknown、needs_review。简历内容被视为不可信数据，模型被要求忽略其中的指令以及敏感个人属性；但仍需人工审核，不能把模型建议当成自动录用或淘汰决定。

示例 JD 已明确要求 Excel 用于财务工作；只有 JD 的 Excel 要求行写明 financial、finance 或 reconciliation 时才启用该上下文约束，不按岗位名称暗中添加要求。英文年限要求会作为独立标准评估，不混入技能覆盖率；薪资、学历/专业资格、工作资格和到岗时间列为人工核实项目。新评估逐项返回 reason、evidence_refs（source、line、text）及 description；补充回答保留 resume_evidence_refs。原有 evidence 和 status 字段兼容保留，页面已展示标准说明，暂未展示理由和行号。旧评估不自动迁移，请新建评估使用新规则。接口字段说明见 agents/README.md。

分数是已有技能证据的加权覆盖率，并非候选人的综合能力或录用概率。缺失信息并不表示不具备能力。姓名、年龄、性别、国籍、照片不作为评分维度，但原文仍保存在本地数据库；本版不声称完成匿名化或公平性认证。经验年限、薪资、学历、工作资格和岗位其他条件暂由人审核。未接入 PDF/DOCX、OCR、邮件或日历；追问只生成草稿，补充回答由演示者录入并确认状态。

两轮后仍缺信息则转人工审核，所有入围或不推进决策均需人操作并记录理由。终态不可直接改写，需新建评估。SQLite 保存状态和行动记录，刷新页面恢复最近一次评估；不是多用户系统，无登录和审批身份验证，仅绑定本机地址，请用虚构数据演示。删除 `data/recruitment.sqlite3` 可清空本地记录（先停止服务）。

下一步可以替换解析器为带结构化输出和原文证据引用的 LLM 适配器，保持评分、状态机与前端 API 不变；随后再扩展文档读取。无需先引入多 Agent 框架、向量数据库或复杂消息队列。
