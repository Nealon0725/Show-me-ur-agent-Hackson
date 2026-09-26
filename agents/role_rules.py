"""Conservative fallback for the catalog's compound criteria.

Every group must have concrete task evidence. Dates alone never establish
relevant employment duration. Unknown criteria go through normal follow-up.
"""
import re

GROUPS = {
    ('JD-001', 'C2'): [r'python|javascript|typescript|node\.?js|flask|django|express', r'\bapi\b|\bapis\b|http|backend|后端|接口'],
    ('JD-001', 'C3'): [r'\bsql\b|postgres|mysql|sqlite|database migration|relational|数据库|数据建模'],
    ('JD-001', 'C4'): [r'\bgit\b|代码审查|代码评审', r'automated.{0,20}test|\bjest\b|\bpytest\b|\bmocha\b|自动化测试'],
    ('JD-002', 'C2'): [r'\bcrm\b|hubspot|salesforce|zoho|pipedrive|dynamics', r'customer|opportunit|pipeline|客户|商机'],
    ('JD-002', 'C3'): [r'pivot|lookup|透视表|查找函数', r'report|sales|pipeline|quotation|报告|报表|销售'],
    ('JD-002', 'C4'): [r'quot|报价', r'follow.up|handover|handed|交接|跟进', r'\bb2b\b|business.to.business|企业客户'],
    ('JD-003', 'C2'): [r'payable|supplier.{0,20}(invoice|payment)|应付', r'receivable|customer.{0,20}(invoice|receipt)|应收'],
    ('JD-003', 'C3'): [r'bank.{0,20}reconcil|银行对账', r'investigat|difference|exception|差异|调查'],
    ('JD-003', 'C4'): [r'excel|spreadsheet|电子表格', r'xero|quickbooks|\bsap\b|accounting software|财务软件', r'financ|invoic|ledger|account|reconcil|财务|会计|对账'],
}
TASK = re.compile(r'\b(built|developed|implemented|maintained|used|prepared|created|performed|processed|posted|updated|wrote|delivered|managed|coordinated|investigated)\b|开发|实现|维护|使用|负责|编写|处理|完成|管理', re.I)
CAUTION = re.compile(r'\b(no|not|never|without|lack|learning|familiar|basic)\b|没有|未曾|不会|学习中', re.I)


def role_fact(rows, criterion):
    key = (criterion['role_id'], criterion['id'])
    patterns = GROUPS.get(key)
    if not patterns:
        refs = [r for r in rows if re.search(r'\b20\d{2}\b|\byears?\b|\bmonths?\b|年|月', r['text'])][:12]
        return {'status': 'unknown', 'evidence': [r['text'] for r in refs], 'evidence_refs': refs,
                'reason': '离线规则无法可靠核实相关工作月份及重叠经历，请补充说明或由人工核实。 / Relevant employment duration requires clarification.'}
    refs = [r for r in rows if any(re.search(p, r['text'], re.I) for p in patterns)]
    concrete = [r for r in refs if TASK.search(r['text']) and not CAUTION.search(r['text'])]
    complete = all(any(re.search(p, r['text'], re.I) for r in concrete) for p in patterns)
    ambiguous = any(CAUTION.search(r['text']) for r in refs)
    status = 'needs_review' if complete and ambiguous else 'evidenced' if complete else 'unknown'
    reason = {'evidenced': '各部分均找到具体工作描述，仍需核对原文。 / Concrete task evidence found for each component.',
              'unknown': '离线规则未能确认全部条件；这不表示缺乏能力。 / Not all components could be established by local rules.',
              'needs_review': '同时存在肯定及限制性描述，需要人工复核。 / Positive and limiting statements require review.'}[status]
    return {'status': status, 'evidence': [r['text'] for r in refs], 'evidence_refs': refs, 'reason': reason}
