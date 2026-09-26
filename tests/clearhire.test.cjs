const {test} = require('node:test');
const assert = require('node:assert/strict');
const {JSDOM, VirtualConsole} = require('jsdom');
const {spawn} = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const net = require('node:net');

const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
async function until(fn) {
  for (let i=0; i<150; i++) { if (await fn()) return; await sleep(20); }
  throw Error('Timed out waiting for UI state');
}

test('uploaded résumé → real API assessment → clarification → decision → reload', async () => {
  const portProbe = net.createServer();
  await new Promise(resolve => portProbe.listen(0,'127.0.0.1',resolve));
  const port = portProbe.address().port;
  await new Promise(resolve => portProbe.close(resolve));
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'clearhire-test-'));
  const server = spawn('python', ['-m','backend.server','--port',String(port),'--db',path.join(temp,'test.sqlite3')],
    {env: {...process.env,RECRUITMENT_AGENT_PROVIDER:'rules'}, stdio: 'ignore'});
  const base = `http://127.0.0.1:${port}`;
  const errors = [], instances = [];
  const calls = [];
  function makeWindow() {
    const vc = new VirtualConsole(); vc.on('jsdomError', e => errors.push(e));
    const dom = new JSDOM('<html><body><div id="app"></div><div id="overlay-root"></div><div id="toast"></div></body></html>',
      {url: base, runScripts:'outside-only', virtualConsole:vc});
    instances.push(dom);
    const w = dom.window;
    w.fetch = async (url,opts) => {calls.push([url,opts?.body]); return fetch(new URL(url,base),opts);};
    w.scrollTo = () => {};
    w.HTMLDialogElement.prototype.showModal = function(){this.setAttribute('open','');};
    w.HTMLDialogElement.prototype.close = function(){this.removeAttribute('open');};
    w.eval(fs.readFileSync('frontend/clearhire/bundle.js','utf8'));
    return w;
  }
  try {
    await until(async () => {try {return (await fetch(base+'/api/workspace')).ok;} catch{return false;}});
    let w = makeWindow(), d = w.document;
    await until(()=>d.querySelector('.demo-pill')?.textContent.includes('本地规则'));
    assert.match(d.body.textContent,/开始分析/);
    d.querySelector('[data-action="import"]').click();
    assert.match(d.querySelector('#file-input').accept,/docx/);
    const file = new w.File(['My own resume\nBuilt Python HTTP APIs.\nDeveloped SQL database migrations.\nUsed Git collaboration and automated software tests.'], 'own-resume.txt', {type:'text/plain'});
    const input = d.querySelector('#file-input');
    Object.defineProperty(input,'files',{value:[file]});
    input.dispatchEvent(new w.Event('change',{bubbles:true}));
    await until(()=>!d.querySelector('#confirm-import').disabled);
    d.querySelector('#confirm-import').click();
    await until(()=>d.querySelector('[data-action="start-run"]'));
    assert.match(d.querySelector('dialog').textContent,/确认岗位标准/);
    d.querySelector('[data-action="start-run"]').click();
    await until(()=>d.querySelector('[data-action="agent-followup"]'));
    assert.match(d.querySelector('#detail-panel').textContent,/own-resume/);
    assert.match(d.querySelector('#detail-panel').textContent,/100%/);
    assert.doesNotMatch(d.querySelector('.detail-summary').textContent,/预设演示/);
    d.querySelector('[data-action="evidence"]').click();
    assert.match(d.querySelector('dialog').textContent,/Agent 判断理由/);
    d.querySelector('[data-action="close-modal"]').click();
    d.querySelector('[data-action="agent-followup"]').click();
    d.querySelector('[name="answer-C1"]').value = '36 months of commercial backend work.';
    d.querySelector('[name="status-C1"]').value = 'evidenced';
    d.querySelector('#agent-followup-form').dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}));
    await until(()=>d.querySelector('[data-action="agent-review"]'));
    d.querySelector('[data-action="agent-review"]').click();
    d.querySelector('[name="decision"]').value='shortlist';
    d.querySelector('[name="reason"]').value='Verified task evidence and employment duration.';
    d.querySelector('#agent-review-form').dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}));
    await until(()=>d.querySelector('#detail-panel')?.textContent.includes('已记录人工决定'));
    d.querySelector('[data-action="agent-events"]').click();
    assert.match(d.querySelector('dialog').textContent,/HUMAN_DECISION/);
    assert.equal(calls.filter(([url])=>url==='/api/runs').length,1);
    assert.match(calls.find(([url])=>url==='/api/runs')[1],/UP-/);
    w = makeWindow(); d = w.document;
    await until(()=>d.querySelector('.demo-pill')?.textContent.includes('本地规则'));
    d.querySelector('[data-action="nav"][data-view="shortlist"]').click();
    assert.match(d.body.textContent,/own-resume/);
    assert.match(d.body.textContent,/Verified task evidence/);
    assert.equal(errors.length,0,errors.map(e=>e.stack).join('\n'));
  } finally {
    for (const dom of instances) dom.window.close();
    server.kill();
    await new Promise(resolve => server.exitCode !== null ? resolve() : server.once('exit',resolve));
    assert.equal(path.dirname(path.resolve(temp)), path.resolve(os.tmpdir()));
    assert.ok(path.basename(temp).startsWith('clearhire-test-'));
    fs.rmSync(temp,{recursive:true,force:true});
  }
});
