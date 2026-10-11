// Start a REAL run and click the queue ✕ and run ✕ while it streams.
const { spawn } = require('child_process');
const http = require('http');
const CHROME = '/usr/bin/google-chrome';
const PORT = 9343;
const URL = 'http://localhost:8000/';
function getJSON(path) {
  return new Promise((resolve, reject) => {
    http.get({ host: '127.0.0.1', port: PORT, path }, (res) => { let d = ''; res.on('data', (c) => (d += c)); res.on('end', () => resolve(JSON.parse(d))); }).on('error', reject);
  });
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
(async () => {
  const chrome = spawn(CHROME, ['--headless=new', '--disable-gpu', '--no-sandbox', '--window-size=1400,900', `--remote-debugging-port=${PORT}`, '--user-data-dir=/tmp/cdp-realrun', URL], { stdio: 'ignore' });
  let targets = [];
  for (let i = 0; i < 50; i++) { try { targets = await getJSON('/json'); if (targets.some((t) => t.type === 'page')) break; } catch (e) {} await sleep(200); }
  const page = targets.find((t) => t.type === 'page');
  const ws = new WebSocket(page.webSocketDebuggerUrl);
  let id = 0; const pending = new Map();
  ws.addEventListener('message', (ev) => { const m = JSON.parse(ev.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } });
  await new Promise((r) => ws.addEventListener('open', r));
  const send = (method, params) => new Promise((resolve) => { const i = ++id; pending.set(i, resolve); ws.send(JSON.stringify({ id: i, method, params })); });
  const evalJS = async (expression) => (await send('Runtime.evaluate', { expression, returnByValue: true })).result.result.value;
  await send('Runtime.enable');
  await sleep(2500);

  // Queue two ideas; start a real run from one, leave the other queued.
  await evalJS(`(() => {
    const S = window.Hack.store.state;
    S.evaluation.queue = []; S.evaluation.runs = [];
    S.levels.push({ level: 1, ideas: [
      { id: 'idea-a', text: 'Use homomorphic encryption to run analytics on encrypted customer data', level: 1 },
      { id: 'idea-b', text: 'A second idea that stays queued', level: 1 },
    ], iteration: null, pending: false, error: null });
    window.Hack.actions.queueIdeaForEvaluation('idea-a');
    window.Hack.actions.queueIdeaForEvaluation('idea-b');
    return 'ok';
  })()`);
  await sleep(300);
  // Start the run from the first queued item.
  await evalJS(`(() => { const q = window.Hack.store.state.evaluation.queue[0]; window.Hack.actions.startQueuedEvaluation(q.id); return 'ok'; })()`);
  await sleep(1500);
  await evalJS('window.Hack.actions.closeModal()');
  await sleep(500);
  console.log('queue len: ' + await evalJS('window.Hack.store.state.evaluation.queue.length'));
  console.log('runs len: ' + await evalJS('window.Hack.store.state.evaluation.runs.length'));
  console.log('run status: ' + await evalJS('window.Hack.store.state.evaluation.runs[0] && window.Hack.store.state.evaluation.runs[0].status'));

  async function clickSel(sel) {
    const pt = await evalJS(`(() => { const b = document.querySelector(${JSON.stringify(sel)}); if (!b) return null; const r = b.getBoundingClientRect(); return { x: r.x + r.width/2, y: r.y + r.height/2 }; })()`);
    if (!pt) return 'no button';
    await send('Input.dispatchMouseEvent', { type: 'mousePressed', x: pt.x, y: pt.y, button: 'left', clickCount: 1 });
    await sleep(25);
    await send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: pt.x, y: pt.y, button: 'left', clickCount: 1 });
    await sleep(250);
    return 'clicked';
  }

  // Click the queue ✕ while the run streams.
  console.log('queue x: ' + await clickSel('#col-evaluation .eval-target .mini-btn'));
  console.log('queue len after: ' + await evalJS('window.Hack.store.state.evaluation.queue.length'));
  console.log('queue nodes after: ' + await evalJS('document.querySelectorAll("#col-evaluation .eval-target").length'));

  // Click the run ✕ while it streams.
  console.log('run x: ' + await clickSel('#col-evaluation .run-card .run-head-right .mini-btn'));
  console.log('runs len after: ' + await evalJS('window.Hack.store.state.evaluation.runs.length'));
  console.log('run nodes after: ' + await evalJS('document.querySelectorAll("#col-evaluation .run-card").length'));
  console.log('modalOpen: ' + await evalJS('window.Hack.store.state.ui.modal.open'));

  // Stop the backend run so we don't leave it running.
  await evalJS(`(() => { const r = window.Hack.store.state.evaluation.runs[0]; if (r && r._handle) r._handle.cancel(); return 'ok'; })()`);
  ws.close(); chrome.kill();
})();
