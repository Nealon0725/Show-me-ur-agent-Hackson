# 会计岗位：三份示例简历的人工验收基准

预期判断依据 `data/demo.json` 原文与本次讨论的岗位标准人工编写，不是独立模型调用结果。2026-09-10 已找到可用的 Python 3.14.3，执行现有 5 项测试全部通过，并实际调用解析器和评估器验证下文的规则结果。

## 评估范围

必需：Excel 财务相关使用经验、Xero 使用经验、记账经验、开票经验。优先：GST 相关经验。每项使用满足、不满足、信息不足、存在矛盾四种判断。“满足”仅表示简历提供了相关自述证据，不代表经历已经核验。

Excel 财务场景是本次讨论确认的细化标准，示例 JD 已同步写明。工作年限现已作为单独标准评估，但不混入技能覆盖率；薪资及其他要求由招聘者人工核实。不得将本轮结果当成完整岗位适配结论。

## 逐项预期结果

| 要求 | A / C001 | B / C002 | C / C003 |
| --- | --- | --- | --- |
| Excel 财务相关使用经验 | 满足 | 满足 | 信息不足 |
| Xero 使用经验 | 满足 | 信息不足 | 不满足 |
| 记账经验 | 满足 | 满足 | 信息不足 |
| 开票经验 | 满足 | 满足 | 信息不足 |
| GST 相关经验 | 满足 | 满足 | 信息不足 |

### A / C001

- 原文第 3 行：`Used Excel and Xero for monthly bookkeeping and invoicing.` 支持 Excel、Xero、记账、开票四项。
- 原文第 4 行：`Prepared GST reports for supervisor review.` 支持 GST 相关经验，不推断其能独立完成申报。
- 下一步：提交人工审核，继续核实本轮范围以外的岗位要求。

### B / C002

- 原文第 3 行：`Excel for bookkeeping and invoicing.` 支持 Excel、记账、开票三项。
- 原文第 4 行：`Prepared GST reports. Accounting software experience not specified.` 支持 GST 相关经验，没有提供 Xero 证据。
- Xero 判断为信息不足；不得推断候选人没有使用过 Xero。
- 追问草稿：你是否使用过 Xero？如有，请描述一次实际工作任务、你的职责及使用时间。

### C / C003

- 原文第 3 行：`Excel for office reports.` 仅支持一般办公报表经验，不能确认财务相关使用经验。
- 原文第 4 行：`No Xero experience.` 明确支持 Xero 不满足。
- 记账、开票和 GST 未提及，均为信息不足。
- 追问草稿：你是否使用 Excel 做过财务报表、对账或财务数据整理？请提供具体任务。是否有记账、开票或 GST 相关经历？请分别说明。
- 下一步：将明确缺少 Xero 经验及其余待确认项交招聘者判断，不自动拒绝。

## 改进前的运行结果对照（历史记录）

以下为实际调用 `agents/parsers.py` 和 `agents/screening.py` 得到的结果：

- A：现有规则覆盖率 100，五项 evidenced。
- B：现有规则覆盖率 78，Xero unknown，其余 evidenced。
- C：现有规则覆盖率 22，Excel evidenced、Xero needs_review，其余 unknown。
- C 的 Excel：关键词匹配无法判断是否属于财务场景。
- C 的 Xero：现有代码统一将否定表述交人工复核，未区分明确不满足与矛盾。

后续 Agent 应用上述逐项预期结果验收，不应只验证覆盖率分数。这三个样例仅是最初开发样例，不能代表企业场景中的准确率。

## 第一轮实现验证

已将示例 JD 的 Excel 要求明确为 `Excel for financial tasks`，并实现四类判断、原文行号、理由和针对性追问。`tests/test_screening.py` 验证三份简历的全部逐项预期结果、证据引用、否定与矛盾、上下文约束及补充回答来源。现有与新增测试共 9 项通过。C 的 Excel 现为 unknown、Xero 为 not_met，其余 unknown，覆盖率为 0；这不表示候选人综合能力为零。

## 第二轮实现验证

示例 JD 的 `1–2 years of relevant experience` 现被解析为最低 1 年、目标 2 年的独立标准。A 的 2 年和 B 的 1 年为 evidenced；C 未提供相关年限，为 unknown。少于最低年限的明确相关经历为 not_met，只有年限但无法确认会计/财务场景时为 unknown。学历/专业资格、薪资、工作资格和到岗时间进入 job.human_review_items，不自动评分。
