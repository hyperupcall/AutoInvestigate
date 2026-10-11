// Where does a real click land when the button is rebuilt mid-click?
const { spawn } = require('child_process');
const http = require('http');
const CHROME = '/usr/bin/google-chrome';
const PORT = 9336;
const URL = 'file://' + process.cwd() + '/index.html';
function getJSON(path) {
  return new Promise((resolve, reject) => {
    http.get({ host: '127.0.0.1', port: PORT, path }, (res) => { let d = ''; res.on('data', (c) => (d += c)); res.on('end', () => resolve(JSON.parse(d))); }).on('error', reject);
  });
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
(async () => {
  const chrome = spawn(CHROME, ['--headless=new', '--disable-gpu', '--no-sandbox', '--window-size=1400,900', `--remote-debugging-port=${PORT}`, '--user-data-dir=/tmp/cdp-profile4', URL], { stdio: 'ignore' });
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
  await sleep(1500);

  await evalJS(`(() => {
    window.__clicks = [];
    document.addEventListener('click', (e) => {
      const t = e.target;
      window.__clicks.push((t.tagName || '?') + '.' + (t.className || '') + ' | closestAction=' + (t.closest && t.closest('[data-action]') ? 'yes' : 'no'));
    }, true);
    const S = window.Hack.store.state;
    S.levels.push({ level: 1, ideas: [{ id: 'idea-q', text: 'Queued idea', level: 1 }, { id: 'idea-r', text: 'Running idea', level: 1 }], iteration: null, pending: false, error: null });
    window.Hack.actions.queueIdeaForEvaluation('idea-q');
    window.Hack.actions.startEvaluation({ ideaId: 'idea-r', ideaText: 'Running idea' });
    return 'ok';
  })()`);
  await sleep(400);
  await evalJS('window.Hack.actions.closeModal()');
  await sleep(100);
  const pt = await evalJS(`(() => { const b = document.querySelector('#col-evaluation .eval-target .mini-btn'); const r = b.getBoundingClientRect(); return { x: r.x + r.width/2, y: r.y + r.height/2 }; })()`);
  await send('Input.dispatchMouseEvent', { type: 'mousePressed', x: pt.x, y: pt.y, button: 'left', clickCount: 1 });
  await sleep(20);
  await send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: pt.x, y: pt.y, button: 'left', clickCount: 1 });
  await sleep(150);
  console.log('clicks: ' + JSON.stringify(await evalJS('window.__clicks')));
  console.log('queue: ' + await evalJS('window.Hack.store.state.evaluation.queue.length'));
  ws.close(); chrome.kill();
})();