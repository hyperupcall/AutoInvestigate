// CDP driver: load the real index.html, queue an idea, click the queue ✕, report.
const { spawn } = require('child_process');
const http = require('http');

const CHROME = '/usr/bin/google-chrome';
const PORT = 9333;
const URL = 'file://' + process.cwd() + '/index.html';

function getJSON(path) {
  return new Promise((resolve, reject) => {
    http.get({ host: '127.0.0.1', port: PORT, path }, (res) => {
      let d = '';
      res.on('data', (c) => (d += c));
      res.on('end', () => resolve(JSON.parse(d)));
    }).on('error', reject);
  });
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

(async () => {
  const chrome = spawn(CHROME, [
    '--headless=new', '--disable-gpu', '--no-sandbox', '--window-size=1400,900',
    `--remote-debugging-port=${PORT}`, '--user-data-dir=/tmp/cdp-profile', URL,
  ], { stdio: 'ignore' });

  let targets = [];
  for (let i = 0; i < 50; i++) {
    try { targets = await getJSON('/json'); if (targets.some((t) => t.type === 'page')) break; } catch (e) {}
    await sleep(200);
  }
  const page = targets.find((t) => t.type === 'page');
  if (!page) { console.log('NO PAGE'); chrome.kill(); return; }

  const ws = new WebSocket(page.webSocketDebuggerUrl);
  let id = 0;
  const pending = new Map();
  const logs = [];
  ws.addEventListener('message', (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); }
    if (msg.method === 'Runtime.consoleAPICalled') logs.push('console: ' + msg.params.args.map((a) => a.value).join(' '));
    if (msg.method === 'Runtime.exceptionThrown') logs.push('EXCEPTION: ' + JSON.stringify(msg.params.exceptionDetails.exception));
  });
  await new Promise((r) => ws.addEventListener('open', r));
  const send = (method, params) => new Promise((resolve) => { const i = ++id; pending.set(i, resolve); ws.send(JSON.stringify({ id: i, method, params })); });

  await send('Runtime.enable');
  await sleep(1500);

  const expr = `(() => {
    const out = [];
    const S = window.Hack.store.state;
    S.levels.push({ level: 1, ideas: [
      { id: 'idea-1', text: 'First idea', level: 1 },
      { id: 'idea-2', text: 'Second idea', level: 1 },
      { id: 'idea-3', text: 'Third idea', level: 1 },
    ], iteration: null, pending: false, error: null });
    window.Hack.actions.queueIdeaForEvaluation('idea-1');
    window.Hack.actions.queueIdeaForEvaluation('idea-2');
    window.Hack.actions.queueIdeaForEvaluation('idea-3');
    out.push('queue after enqueue: ' + S.evaluation.queue.length);
    const targets = document.querySelectorAll('#col-evaluation .eval-target');
    out.push('targets: ' + targets.length);
    // click the x of the SECOND item
    const btn = targets[1].querySelector('.mini-btn');
    out.push('second x: ' + (btn ? btn.textContent : 'none'));
    if (btn) btn.click();
    out.push('queue after click: ' + S.evaluation.queue.length);
    out.push('texts: ' + S.evaluation.queue.map((q) => q.text).join(','));
    out.push('nodes after click: ' + document.querySelectorAll('#col-evaluation .eval-target').length);
    return out.join(' | ');
  })()`;
  const res = await send('Runtime.evaluate', { expression: expr, returnByValue: true });
  console.log('RESULT: ' + JSON.stringify(res.result && res.result.result && res.result.result.value));
  console.log('LOGS: ' + JSON.stringify(logs));
  ws.close();
  chrome.kill();
})();