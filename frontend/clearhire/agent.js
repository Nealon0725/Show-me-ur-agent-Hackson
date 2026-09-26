// Integration with the local recruitment workflow; bundled after main.js.
const connection = {ready: false, mode: 'rules', model: null, busy: false};
let pendingBatch = [], pendingRun = null;
const runCache = new Map();

async function agentApi(path, body) {
  let response;
  try {
    response = await fetch(path, body === undefined ? {} : {
      method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)
    });
  } catch { throw Error(t('Cannot reach the local server. Start python -m backend.server.', '无法连接本地服务，请运行 python -m backend.server。')); }
  const data = await response.json().catch(() => ({error: t('Invalid server response.', '服务响应异常，请确认使用的是后端地址。')}));
  if (!response.ok) throw Error(data.error || `HTTP ${response.status}`);
  return data;
}

function applyRun(run) {
  runCache.set(run.id, run);
  for (const item of run.candidates) {
    const c = candidates.find(x => x.id === item.source_id);
    if (!c) continue;
    c.runId = run.id; c.agentId = item.id; c.agent = item;
    const evaluation = item.evaluation;
    if (evaluation) {
      const states = {evidenced: 'demonstrated', not_met: 'explicitly_not_met', unknown: 'not_evidenced', needs_review: 'unclear'};
      c.criteria = evaluation.details.map(d => ({
        criterion_id: d.id, title: d.description || d.label, status: states[d.status],
        source_section: t('Resume / follow-up', '简历 / 补充回答'),
        evidence_quote: (d.evidence_refs || []).map(r => `${r.source === 'followup' ? t('Follow-up', '补充回答') : t('Line ', '第 ') + r.line + t('', ' 行')}：${r.text}`).join('\n'),
        interpretation: d.reason
      }));
      c.label = evaluation.details.every(d => d.status === 'evidenced') ? 'evidence_complete'
        : ['REQUEST_INFO', 'HUMAN_REVIEW'].includes(evaluation.action) ? 'needs_clarification'
        : evaluation.details.some(d => d.status === 'evidenced') ? 'evidence_partial' : 'evidence_limited';
    } else { c.criteria = []; c.label = 'pending'; }
    // Backend decisions, not local stars, are authoritative for assessed candidates.
    if (item.decision?.decision === 'shortlist') S.shortlist.add(c.id);
    else S.shortlist.delete(c.id);
  }
}

async function loadWorkspace() {
  const workspace = await agentApi('/api/workspace');
  connection.mode = workspace.mode; connection.model = workspace.model; connection.ready = true;
  for (const c of workspace.uploads) {
    const existing = candidates.find(x => x.id === c.id);
    if (existing) Object.assign(existing, c); else candidates.push(c);
  }
  for (const run of workspace.runs) applyRun(run);
  render();
}

function showAgentError(error) {
  modal(t('Action could not finish', '操作未完成'), `<p role="alert">${esc(error.message)}</p>`, done());
}

const originalShell = shell;
shell = function(main) {
  const markup = originalShell(main);
  const mode = connection.ready ? connection.mode === 'model'
    ? t('Connected model', '已连接模型') : t('Local rules', '本地规则模式')
    : t('Connecting…', '连接中…');
  return markup.replace(/<span class="pill demo-pill"[\s\S]*?<\/span>/,
    `<span class="pill demo-pill">${icon('grid')}${mode}</span>`);
};

const originalDetail = detail;
detail = function() {
  let html = originalDetail();
  const c = selected();
  if (!c) return html;
  const assessed = !!c.agent?.evaluation;
  const note = assessed
    ? t('Agent result saved locally. Verify evidence before deciding.', 'Agent 结果已保存到本地，请核对证据后再做决定。')
    : c.runId ? t('Confirm the role requirements to continue.', '请确认岗位标准后继续评估。')
    : c.synthetic ? t('Prepared sample preview. Run analysis to obtain an Agent result.', '当前为预设样本预览，点击开始分析获取 Agent 实际结果。')
    : t('Text extracted and saved locally. Ready for analysis.', '已提取文字并保存到本地，可以开始分析。');
  html = html.replace(/(<div class="detail-summary[^]*?<p>)[^]*?(<\/p><\/div>)/, `$1${esc(note)}$2`);
  html = html.replace(/<div class="footer-hint">[^]*?<\/div>/,
    `<div class="footer-hint">${t('Agent decisions are saved locally with a reason.', 'Agent 人工决定连同理由保存到本地。')}</div>`);
  return html;
};

const originalEvidenceBody = evidenceBody;
evidenceBody = function(c) {
  if (!c.agent?.evaluation) return (c.label === 'pending' ?
    empty(t('Ready for analysis', '可以开始分析'), t('Review the extracted text, then confirm the role requirements.', '先检查提取的简历文字，再确认岗位标准。'), btn('analyse-one',t('Analyse this résumé','分析这份简历'),'play',true,`data-id="${c.id}"`)) : originalEvidenceBody(c));
  const v = c.agent.evaluation;
  const action = {SHORTLIST: t('Ready for human review', '建议入围，待人工审核'), REQUEST_INFO: t('Clarification needed', '需要补充信息'), HUMAN_REVIEW: t('Human review needed', '需要人工复核'), LOW_MATCH: t('Required evidence not met', '必需条件不满足，待人工审核'), COMPLETE: t('Decision recorded', '已记录人工决定')}[c.agent.action];
  const scores = `<div class="agent-summary"><strong>${esc(action || c.agent.action)}</strong><p>${t('Documented / possible skill coverage', '已有 / 可能技能证据覆盖率')}：${v.documented_score ?? '—'}% / ${v.possible_score ?? '—'}%</p><p>${t('Evidence completeness', '证据完整度')}：${v.evidence_completeness ?? '—'}% · ${esc(v.parser)}</p><p>${t('Rank within this assessment', '本次评估内排名')} ${v.rank ?? '—'} · ${v.rank_status === 'provisional' ? t('Provisional', '暂定') : t('Current evidence', '当前证据')}</p></div>`;
  let controls = '';
  if (c.agent.action === 'REQUEST_INFO') controls = btn('agent-followup',t('Record answers and reassess','补充回答并重新评估'),'note',true,`data-id="${c.id}"`);
  if (['SHORTLIST','LOW_MATCH','HUMAN_REVIEW'].includes(c.agent.action)) controls += btn('agent-review',t('Human review','人工审核'),'check',true,`data-id="${c.id}"`);
  if (c.agent.decision) controls += `<p>${t('Decision','人工决定')}：${esc(c.agent.decision.decision)} — ${esc(c.agent.decision.reason)}</p>`;
  return scores + originalEvidenceBody(c) + controls + btn('agent-events',t('Action history','Agent 行动记录'),'file',false,`data-id="${c.id}"`);
};

toggleShortlist = function(id) {
  const c = candidates.find(x => x.id === id);
  if (c?.agent?.decision) return modal(t('Decision recorded','决定已记录'), `<p>${esc(c.agent.decision.reason)}</p><p>${t('Create a new assessment to reconsider this decision.','如需重新决定，请重新分析，创建新的评估。')}</p>`, done());
  if (['SHORTLIST','LOW_MATCH','HUMAN_REVIEW'].includes(c?.agent?.action)) return reviewModal(c);
  modal(t('Complete the assessment first','请先完成评估'), `<p>${t('Analyse the résumé and answer any required clarifications before recording a hiring decision.','请先分析简历，并完成必要的补充信息，再记录人工决定。')}</p>`, done());
};

function openAnalysis(cs) {
  if (!connection.ready) return showAgentError(Error(t('Server is not connected. Reload after starting the backend.','后端尚未连接，请启动后端后刷新页面。')));
  if (!cs.length) return showAgentError(Error(t('No candidates selected.','没有待分析的简历。')));
  if (cs.length > 60) return showAgentError(Error(t('Select at most 60 candidates.','每次最多分析 60 人，请勾选候选人。')));
  pendingBatch = cs.map(c => c.id); pendingRun = null;
  const j = job();
  const mode = connection.mode === 'model'
    ? t('The configured model service will receive résumé text and these requirements.', '分析时会将简历文字及以下岗位标准发送给已配置的模型服务。')
    : t('Local rules run on this computer. Dates and ambiguous evidence require clarification.', '当前在本机运行离线规则；工作月份和不明确的证据需要补充或人工核实。');
  modal(t('Confirm requirements and analyse', '确认岗位标准并分析'),
    `<p>${esc(jtitle(j))} · ${cs.length} ${t('résumés','份简历')}</p><ol>${j.criteria.map(([id, text]) => `<li><strong>${esc(id)}</strong> ${esc(text)}</li>`).join('')}</ol>${callout(esc(mode))}<p>${t('Experience is assessed separately from skill coverage. All final decisions remain human.', '经验条件单独评估，不计入技能覆盖率；最终决定由人工做出。')}</p>`,
    btn('close-modal',t('Cancel','取消')) + btn('start-run',t('Confirm and analyse','确认标准，开始分析'),'play',true));
}

runModal = function() {
  const checked = pool().filter(c => S.checked.has(c.id));
  const uploaded = pool().filter(c => !c.synthetic && !c.agent?.evaluation);
  openAnalysis(checked.length ? checked : uploaded.length ? uploaded : pool());
};

startRun = async function() {
  if (connection.busy) return;
  connection.busy = true;
  modal(t('Analysing résumés','正在分析简历'), `<p role="status">${t('The Agent is evaluating the confirmed requirements. Please keep this page open.','Agent 正在根据已确认的标准逐项评估，请保持页面打开。')}</p>`);
  S.running = true;
  document.querySelector('[data-action="close-modal"]').disabled = true;
  try {
    if (!pendingRun) pendingRun = await agentApi('/api/runs', {job_id: S.job, candidate_ids: pendingBatch});
    const run = await agentApi(`/api/runs/${pendingRun.id}/confirm`, {});
    applyRun(run);
    S.filter = 'all'; S.source = 'all'; S.query = ''; S.page = 1;
    S.selected = pendingBatch[0]; S.tab = 'evidence';
    S.running = false; closeModal(); render();
    // The result may fall on a later page after sorting.
    S.page = Math.max(1, Math.floor(filtered().findIndex(c => c.id === S.selected) / 8) + 1); render();
    toast(t('Assessment saved. Review the evidence below.','评估已保存，请核对下方证据。'));
  } catch(error) { S.running = false; showAgentError(error); }
  finally { S.running = false; connection.busy = false; }
};

async function toBase64(file) {
  return new Promise((resolve,reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result.split(',')[1]);
    reader.onerror = () => reject(Error(t('Unable to read file.','无法读取文件。')));
    reader.readAsDataURL(file);
  });
}

confirmImport = async function() {
  if (connection.busy) return;
  const valid = S.queue.filter(x => !x.error);
  if (!valid.length) return;
  connection.busy = true; S.running = true;
  document.querySelector('#confirm-import').disabled = true;
  const imported = [], errors = [];
  try {
    for (const entry of valid) {
      try {
        const c = await agentApi('/api/uploads', {job_id: S.job, name: entry.file.name, content: await toBase64(entry.file)});
        candidates.push(c); imported.push(c);
      } catch(error) { errors.push(`${entry.file.name}: ${error.message}`); }
    }
    S.running = false; closeModal();
    S.view = 'candidates'; S.filter = 'pending'; S.source = 'uploaded'; S.query = ''; S.page = 1;
    if (imported.length) S.selected = imported[0].id;
    render();
    if (errors.length) modal(t('Import results','导入结果'), `<p>${imported.length} ${t('files saved','份文件已保存')}</p><ul>${errors.map(s=>`<li>${esc(s)}</li>`).join('')}</ul>`,done());
    else if (imported.length) openAnalysis(imported);
  } finally { S.running = false; connection.busy = false; }
};

function followupModal(c) {
  modal(t('Record clarification','记录补充回答'), `<form id="agent-followup-form" data-id="${c.id}">${c.agent.evaluation.questions.map(q => `<label>${esc(q.question)}<textarea name="answer-${esc(q.criterion_id)}" maxlength="50000" rows="3"></textarea></label><select name="status-${esc(q.criterion_id)}" aria-label="${esc(q.criterion_id)}"><option value="unknown">${t('Still unclear','仍不明确')}</option><option value="evidenced">${t('Relevant evidence provided','回答提供了相关证据')}</option><option value="not_met">${t('Explicitly not met','回答明确不满足')}</option></select>`).join('')}<button class="btn primary" type="submit">${t('Save and reassess','保存并重新评估')}</button></form>`);
}

function reviewModal(c) {
  modal(t('Human decision','人工决定'), `<form id="agent-review-form" data-id="${c.id}"><label>${t('Decision','决定')}<select name="decision"><option value="hold">${t('Hold','暂缓')}</option><option value="shortlist">${t('Approve shortlist','批准入围')}</option><option value="decline">${t('Do not proceed','不推进')}</option></select></label><label>${t('Reason (required)','理由（必填）')}<textarea name="reason" required maxlength="2000" rows="4"></textarea></label><p>${t('This closes the current assessment for this candidate.','保存后结束该候选人的本次评估。')}</p><button class="btn primary" type="submit">${t('Save decision','保存决定')}</button></form>`);
}

document.addEventListener('submit', async event => {
  const form = event.target;
  if (!['agent-followup-form','agent-review-form'].includes(form.id)) return;
  event.preventDefault();
  if (connection.busy) return;
  const c = candidates.find(x=>x.id===form.dataset.id), fields = new FormData(form);
  let op, payload = {candidate_id: c.agentId};
  if (form.id === 'agent-followup-form') {
    op = 'followup'; payload.answers = {};
    for (const q of c.agent.evaluation.questions) {
      const evidence = String(fields.get('answer-'+q.criterion_id) || '').trim();
      if (evidence) payload.answers[q.criterion_id] = {evidence, status: fields.get('status-'+q.criterion_id)};
    }
    if (!Object.keys(payload.answers).length) return toast(t('Enter at least one answer.','请至少填写一项回答。'));
  } else { op = 'review'; payload.decision = fields.get('decision'); payload.reason = String(fields.get('reason') || '').trim(); }
  connection.busy = true; S.running = true;
  form.querySelector('button[type="submit"]').disabled = true;
  try {
    applyRun(await agentApi(`/api/runs/${c.runId}/${op}`, payload));
    S.running = false; closeModal(); render(); toast(t('Saved locally.','已保存到本地。'));
  } catch(error) {
    // Keep the entered answer/reason available for retry.
    let errorNode = form.querySelector('[role="alert"]');
    if (!errorNode) { errorNode = document.createElement('p'); errorNode.setAttribute('role','alert'); form.append(errorNode); }
    errorNode.textContent = error.message;
  } finally { S.running = false; connection.busy = false; form.querySelector('button[type="submit"]').disabled = false; }
});

document.addEventListener('click', event => {
  const b = event.target.closest('[data-action]');
  if (!b || b.disabled) return;
  const c = candidates.find(x=>x.id===b.dataset.id);
  if (b.dataset.action === 'analyse-one') openAnalysis([c]);
  if (b.dataset.action === 'agent-followup') followupModal(c);
  if (b.dataset.action === 'agent-review') reviewModal(c);
  if (b.dataset.action === 'agent-events') {
    const run = runCache.get(c.runId);
    modal(t('Agent action history','Agent 行动记录'), `<pre class="resume-text">${esc(run.events.filter(e=>!e.candidate_id||e.candidate_id===c.agentId).map(e=>`${e.step}. ${e.action} — ${e.detail || e.reason}`).join('\n'))}</pre>`,done());
  }
});

helpModal = function() {
  modal(t('Connected review workspace','已接入 Agent 的评审工作台'), `<ol><li>${t('Choose a role, then upload your résumé or select sample candidates.','选择岗位，上传自己的简历或勾选样本候选人。')}</li><li>${t('Confirm all role requirements and start analysis.','确认完整岗位标准，开始分析。')}</li><li>${t('Inspect evidence, record clarification answers, then make a human decision.','核对证据，补充回答，再记录人工决定。')}</li></ol><p>${t('Files and assessments are saved on this computer. Reviewer notes stay in this browser. Scanned PDFs require a text layer.','文件与评估保存在本机，评审备注保存在当前浏览器。扫描 PDF 需要先转换成带文字层的文件。')}</p>`,done());
};

loadWorkspace().catch(error => {render(); showAgentError(error);});
