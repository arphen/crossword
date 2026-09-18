import { existsSync } from 'node:fs';
import { spawnSync } from 'node:child_process';

const url = process.env.LEGACY_SMOKE_URL ?? process.argv[2] ?? 'http://127.0.0.1:5001/legacy/';
const candidates = [
  process.env.CHROME_BIN,
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  '/Applications/Chromium.app/Contents/MacOS/Chromium',
  '/usr/bin/google-chrome',
  '/usr/bin/chromium',
  '/usr/bin/chromium-browser',
].filter(Boolean);
const browser = candidates.find((candidate) => existsSync(candidate));

if (!browser) {
  console.error(
    'Legacy browser smoke skipped: Chrome/Chromium was not found. ' +
    'Set CHROME_BIN to run it on a supported browser runner.',
  );
  process.exit(77);
}

const result = spawnSync(browser, [
  '--headless=new',
  '--no-sandbox',
  '--disable-gpu',
  '--disable-dev-shm-usage',
  '--dump-dom',
  '--virtual-time-budget=3000',
  // The smoke server serves the puzzle locally. Prevent an accidental request
  // if the app ever regresses to its provider route.
  '--host-resolver-rules=MAP nytsyn.pzzl.com ~NOTFOUND',
  url,
], { encoding: 'utf8', timeout: 15000, maxBuffer: 10 * 1024 * 1024 });

if (result.error) {
  console.error(`Could not launch ${browser}: ${result.error.message}`);
  process.exit(1);
}
if (result.status !== 0) {
  console.error(result.stderr || `Browser exited with status ${result.status}`);
  process.exit(result.status ?? 1);
}

const dom = result.stdout;
const required = ['id="app"', 'vue.js', 'axios.min.js', 'socket.io.min.js'];
for (const marker of required) {
  if (!dom.includes(marker)) {
    console.error(`Legacy browser smoke failed: missing ${marker}`);
    process.exit(1);
  }
}

// Vue 2 compiles these directives and custom delimiters out of the live DOM.
// Seeing one means the page rendered as an inert Jinja/HTML template.
const unmountedMarkers = ['[[', ']]', 'v-if=', 'v-for=', ':class=', '@click='];
for (const marker of unmountedMarkers) {
  if (dom.includes(marker)) {
    console.error(`Legacy browser smoke failed: Vue marker remains: ${marker}`);
    process.exit(1);
  }
}

console.log(`Legacy browser smoke passed in ${browser}: Vue mounted at ${url}`);
