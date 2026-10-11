// Click the ✕ on a run card (past run) against the LIVE backend.
const { spawn } = require('child_process');
const http = require('http');
const CHROME = '/usr/bin/google-chrome';
const PORT = 9342;
const URL = 'http://localhost:8000/';
function getJSON(path) {
  return new Promise((resolve, reject) => {
    http.get({ host: '127.0.0.1', port: PORT, path }, (res) => { let d = ''; res.on('data', (c) => (d += c)); res.on('end', () => resolve(JSON.parse(d))); }).on('error', reject);
  });
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
(async () => {
  const chrome = spawn(CHROME, ['--headless=new', '--disable-gpu', '--no-sandbox', '--window-size=1400,900', `--remote-debugging-port=${PORT}`, '--user-data-dir=/tmp/cdp-live2', URL], { stdio: 'ignore' });
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

  const before = await evalJS('window.Hack.store.state.evaluation.runs.length');
  console.log('runs before: ' + before);
  const pt = await evalJS(`(() => { const b = document.querySelector('#col-evaluation .run-card .run-head-right .mini-btn'); if (!b) return null; const r = b.getBoundingClientRect(); return { x: r.x + r.width/2, y: r.y + r.height/2 }; })()`);
  console.log('run x point: ' + JSON.stringify(pt));
  if (pt) {
    await send('Input.dispatchMouseEvent', { type: 'mousePressed', x: pt.x, y: pt.y, button: 'left', clickCount: 1 });
    await sleep(20);
    await send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: pt.x, y: pt.y, button: 'left', clickCount: 1 });
    await sleep(300);
  }
  console.log('runs after: ' + await evalJS('window.Hack.store.state.evaluation.runs.length'));
  console.log('run nodes after: ' + await evalJS('document.querySelectorAll("#col-evaluation .run-card").length'));
  console.log('modalOpen: ' + await evalJS('window.Hack.store.state.ui.modal.open'));

  ws.close(); chrome.kill();
})();
