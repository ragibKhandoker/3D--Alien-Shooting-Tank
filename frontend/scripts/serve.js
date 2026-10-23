// Starts the AngularJS dev server (http-server) on port 4200 with /api proxied to Flask.
// If 4200 is already serving this frontend (npm start run twice), reuse it instead of crashing.
// If another program holds 4200, use the next free port.
// With --open, the browser opens only after the Flask backend answers.
const http = require('http');
const net = require('net');
const path = require('path');
const { spawn } = require('child_process');

const PREFERRED_PORT = Number(process.env.FRONTEND_PORT) || 4200;
const BACKEND = process.env.BACKEND_URL || 'http://127.0.0.1:5000';
const ROOT = path.join(__dirname, '..');
const openBrowser = process.argv.includes('--open');

function isFree(port) {
  return new Promise(resolve => {
    const probe = net.createServer()
      .once('error', () => resolve(false))
      .once('listening', () => probe.close(() => resolve(true)))
      .listen(port, '0.0.0.0');
  });
}

function isOurFrontend(port) {
  return new Promise(resolve => {
    const req = http.get({ host: '127.0.0.1', port, path: '/', timeout: 2000 }, res => {
      let body = '';
      res.setEncoding('utf8');
      res.on('data', chunk => { body += chunk; });
      res.on('end', () => resolve(body.includes('ng-app="tankApp"')));
    });
    req.on('timeout', () => req.destroy());
    req.on('error', () => resolve(false));
  });
}

function backendReady() {
  return new Promise(resolve => {
    const req = http.get(BACKEND + '/api/health', { timeout: 2000 }, res => {
      res.resume();
      resolve(res.statusCode === 200);
    });
    req.on('timeout', () => req.destroy());
    req.on('error', () => resolve(false));
  });
}

// Open the browser only once Flask answers, so the page never starts with "Backend is offline"
async function openWhenBackendReady(url) {
  const deadline = Date.now() + 60000;
  let warned = false;
  while (!(await backendReady())) {
    if (!warned) {
      console.log(`Waiting for the Flask backend (${BACKEND}) before opening the browser...`);
      warned = true;
    }
    if (Date.now() > deadline) {
      console.log(`Backend did not start in 60 s. Check the [backend] lines above, then open ${url} yourself.`);
      return;
    }
    await new Promise(r => setTimeout(r, 1000));
  }
  console.log(`Backend is ready. Opening ${url}`);
  const opener = process.platform === 'win32' ? ['cmd', ['/c', 'start', '""', url]]
    : process.platform === 'darwin' ? ['open', [url]] : ['xdg-open', [url]];
  spawn(opener[0], opener[1], { stdio: 'ignore', detached: true }).unref();
}

async function main() {
  let port = PREFERRED_PORT;
  if (!(await isFree(port))) {
    if (await isOurFrontend(port)) {
      console.log(`Frontend is already running at http://127.0.0.1:${port}; reusing it.`);
      if (openBrowser) { await openWhenBackendReady(`http://127.0.0.1:${port}`); }
      return;
    }
    console.log(`Port ${port} is used by another program, looking for a free port...`);
    while (!(await isFree(++port))) {
      if (port > PREFERRED_PORT + 20) {
        console.error(`No free port between ${PREFERRED_PORT} and ${port}. Close some programs and try again.`);
        process.exit(1);
      }
    }
  }

  const cli = require.resolve('http-server/bin/http-server');
  // --no-deprecation: http-proxy (inside http-server) uses an old Node API and would print a warning
  const args = ['--no-deprecation', cli, ROOT, '-p', String(port), '-c-1', '-P', BACKEND, '--silent'];
  console.log(`Frontend running at http://127.0.0.1:${port}  (API -> ${BACKEND})`);

  const child = spawn(process.execPath, args, { stdio: 'inherit' });
  const stop = () => child.kill();
  process.on('SIGINT', stop);
  process.on('SIGTERM', stop);
  child.on('exit', code => process.exit(code || 0));

  if (openBrowser) { openWhenBackendReady(`http://127.0.0.1:${port}`); }
}

main();
