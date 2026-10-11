// CDP driver: load artifactfactory.html and report the factory status badge + console.
const { spawn } = require('child_process');
const http = require('http');

const CHROME = '/usr/bin/google-chrome';
const PORT = 9344;
const URL = process.argv[2] || ('file://' + process.cwd() + '/artifactfactory.html');

function getJSON(path) {
  return new Promise((resolve, reject) => {
    http.get({ host: '127.0.0.1', port: PORT, path }, (res) => {
      let d = ''; res.on('data', (c) => (d += c)); res.on('end', () => resolve(JSON.parse(d)));
    }).on('error', reject);
  });
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

(async () => {
  const chrome = spawn(CHROME, [
    '--headless=new', '--disable-gpu', '--no-sandbox', '--window-size=1400,900',
    `--remote-debugging-port=${PORT}`, '--user-data-dir=/tmp/af-probe', URL,
  ], { stdio: 'ignore' });

  let targets = [];
  for (let i = 0; i < 50; i++) {
    try { targets = await getJSON('/json'); if (targets.some((t) => t.type === 'page')) break; } catch (e) {}
    await sleep(200);
  }
  const page = targets.find((t) => t.type === 'page');
  if (!page) { console.log('NO PAGE'); chrome.kill(); return; }

  const ws = new WebSocket(page.webSocketDebuggerUrl);
  let id = 0; const pending = new Map(); const logs = [];
  ws.addEventListener('message', (ev) => {
    const m = JSON.parse(ev.data);
    if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); }
    if (m.method === 'Runtime.consoleAPICalled') logs.push('console: ' + m.params.args.map((a) => a.value).join(' '));
    if (m.method === 'Runtime.exceptionThrown') logs.push('EXCEPTION: ' + JSON.stringify(m.params.exceptionDetails.exception));
  });
  await new Promise((r) => ws.addEventListener('open', r));
  const send = (method, params) => new Promise((resolve) => { const i = ++id; pending.set(i, resolve); ws.send(JSON.stringify({ id: i, method, params })); });
  await send('Runtime.enable');
  await sleep(2500);

  const expr = `(() => {
    const badge = document.getElementById('factory-status');
    const body = document.getElementById('factory-body');
    return JSON.stringify({
      badge: badge ? badge.textContent : null,
      badgeTitle: badge ? badge.title : null,
      body: body ? body.textContent.slice(0, 200) : null,
    });
  })()`;
  const res = await send('Runtime.evaluate', { expression: expr, returnByValue: true });
  console.log('URL: ' + URL);
  console.log('RESULT: ' + (res.result && res.result.result && res.result.result.value));
  console.log('LOGS: ' + JSON.stringify(logs));
  ws.close(); chrome.kill();
})();