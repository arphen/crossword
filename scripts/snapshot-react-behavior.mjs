// Mechanical, reviewable behavior snapshot for phase-one parity. No Vue runtime is imported.
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
const target = new URL('../apps/react/src/behavior/', import.meta.url);
mkdirSync(target, { recursive: true });
const desktop = readFileSync(new URL('../src/crossword/static/main.js', import.meta.url), 'utf8');
const mobile = readFileSync(new URL('../src/crossword/static/mobile.js', import.meta.url), 'utf8');
const dependencies = '{ axios, socket, ROOM_ID, INITIAL_ROLE, setTimeout, clearTimeout, setInterval, clearInterval, requestAnimationFrame, cancelAnimationFrame }';
const desktopObject = desktop.slice(desktop.indexOf('const CrosswordApp = ') + 'const CrosswordApp = '.length, desktop.indexOf('\n// Initialize Vue app')).trim().replace(/;$/, '').replaceAll('Vue.set(', 'this.$set(');
const mobileObject = mobile.slice(mobile.indexOf('new Vue(') + 'new Vue('.length).trim().replace(/\);$/, '');
for (const [name, object] of [['desktop', desktopObject], ['mobile', mobileObject]]) {
  writeFileSync(new URL(`${name}.js`, target), `// Mechanically ported from the curated Vue ${name} behavior.\n// Regenerate with node scripts/snapshot-react-behavior.mjs; original files remain unchanged.\nexport function createOptions(${dependencies}) {\n  return ${object};\n}\n`);
}
