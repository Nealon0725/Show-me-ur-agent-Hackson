# 数据字典与接入约定

## 输入

JSON/JSONL/TXT 使用 UTF-8；CSV 使用带 BOM 的 UTF-8，方便 Excel 打开。程序读取 CSV 时建议使用 `utf-8-sig`。JSONL 每一行都是独立 JSON 对象，没有外层数组。

`inputs/resumes.jsonl` 每条记录有：

| 字段 | 类型 | 定义 |
|---|---|---|
| candidate_id | string | 稳定候选人 ID，如 CV-001；没有等级编码 |
| job_id | string | 本次申请的岗位 ID，如 JD-001 |
| resume_text | string | 原始英文简历全文；保留段落和换行 |

`inputs/applications.csv` 是申请关联表：`candidate_id`、`job_id`、`pdf_path`。`inputs/manifest.csv` 额外包括 `txt_path`、`pdf_type`、`page_count`、`sha256`、`data_origin`。文件路径相对数据包根目录；哈希针对交付的 PDF 字节。

`pdf_type`：`single_column_pdf`、`two_column_pdf`、`image_only_pdf`。三者分别表示单栏文本、双栏文本、无文本层的扫描式 PDF。`data_origin` 全部为 `synthetic`。

`inputs/jobs/jobs.json` 是三个岗位的数组，包含 ID、英文名称、虚拟公司、岗位目的、`minimum_months`、`criteria`、`preferred`、`education`、`responsibilities`。`criteria` 中每项是 `[条目ID, 英文定义]`。匹配时条目键使用 `(job_id, criterion_id)`；不能认为不同岗位的 C2 有相同含义。

最小读取示例（从解压后的数据包目录运行）：

```python
import json
from pathlib import Path

root = Path('.')
jobs = {j['job_id']: j for j in json.loads(
    (root / 'inputs/jobs/jobs.json').read_text(encoding='utf-8'))}
for line in (root / 'inputs/resumes.jsonl').read_text(encoding='utf-8').splitlines():
    item = json.loads(line)
    job = jobs[item['job_id']]
    # 将 item['resume_text'] 与 job 交给你们的筛选流程。
    # PDF/OCR 测试改为读取 applications.csv 中的 pdf_path。
    print(item['candidate_id'], job['title'])
```

## 提取参考

`evaluation/extraction_reference.jsonl` 是作者参考数据，不是解析器已经跑出的结果。

| 字段 | 含义 |
|---|---|
| full_name / email / location | 简历明示的姓名、邮箱和地点；不要由地点推断国籍或工作资格 |
| skills | 作者列出的技能字符串数组，不表示每项都有工作证据 |
| experience | 工作经历对象数组：title、employer、start_month、end_month、bullets |
| education_text / certification_text | 教育、证书的原文参考；未列专业证书时有明确文字说明 |
| project_text | 选取的项目或过程改善描述 |
| observed_dated_role_months | 已列岗位的可计算日历月份，不区分是否与目标岗位相关 |
| reference_relevant_months | 按该岗位口径、从简历可确认的相关月份；不是对真实职业生涯的调查结论 |
| as_of_date | 固定截止日 2026-08-31 |

月份使用 `YYYY-MM`，缺少起始年月为 JSON `null`，不能改成 0、空日期或自行猜测。由于每份简历目前只有一段主要列明的任职期间，月份按结束月减开始月再加 1 计算。例如 2024-09 至 2026-08 为 24 个月。月份计数不是工时或 FTE 年资。

任职起始日缺失时，两个月份指标均为 null。简介声称的总年资与唯一列出的任职期冲突时，仍记录 `observed_dated_role_months`，但 `reference_relevant_months` 设为 null，并要求澄清。完全不相关的任职可以有较长的 observed 月份，但没有可确认的相关月份；0 不等于候选人没有其他未列出的经历。

个人项目、学习和工作空档不计入商业经验。工作空档不会扣减此前已经获得的相关月份。后续补入多段经历时，须合并重叠月份，不能直接相加；本版本没有设计多段重叠任职案例。

## 筛选参考

`evaluation/screening_reference.jsonl` 每个候选人–岗位一条，包含：

- `candidate_id`、`job_id`：关联输入。
- `split`：development、holdout 或 demo。
- `reference_label`：证据覆盖状态，详见 README；不表示应聘结果。
- `case_type`：测试案例类型，仅供评测。
- `criteria`：四项状态，包含 criterion_id、status、source_section、evidence_quote、interpretation。
- `review_question_zh`：需要追问时的中文建议；否则为空字符串。
- `annotator`：AI 初始参考，待团队复核。

`evidence_quote` 是输入简历中的原文片段；日期冲突的第一项引用简介，并在解释中指出与列出月份的差异。它不是外部背调结果，也不证明虚拟简历中的经历真实发生。

`screening_reference.csv` 是相同判断的扁平版，C1–C4 各一列。`criterion_evidence.csv` 是逐项展开的 240 行。`splits.csv` 和三份 `*_ids.csv` 给出阶段划分。

四项状态仅接受：`demonstrated`、`not_evidenced`、`explicitly_not_met`、`unclear`。汇总等级按 README 的优先顺序计算，不使用姓名、学校声誉、身份推断、年龄或性别。

`prediction_example.json` 只展示系统输出字段形状，里面的 ID 是占位符，不是一位额外候选人。示例包含 C1–C4 全部四项，使用 `predicted_label` 表示模型预测，避免与参考答案的 `reference_label` 混淆。空引用和占位解释必须替换为实际系统输出。

## 更新约定

以 candidate_id 为主键关联同一候选人，以 candidate_id + job_id 关联某次岗位判断。若改动 PDF 内容，必须同步更新 TXT、JSONL、字段参考、证据引用和 PDF 哈希。若只改岗位 JD，也应重新审查其下所有筛选参考，提取参考通常可保留。

所有 reference 文件应由评测端读取。尤其不能让检索组件将 `case_type`、`reference_label`、split、答案工作簿或原文证据表拼入候选人的提示词。为了测试 OCR，需将作者 TXT 与实际解析输出保存在不同位置。
