// Rasterise each SVG at its own natural size, plus a contact sheet so every mark can be looked at
// before it ships. A logo that has not been rendered and inspected is a guess.
import { createRequire } from 'node:module';
import { pathToFileURL, fileURLToPath } from 'node:url';
import { dirname } from 'node:path';
import { readdirSync, readFileSync } from 'node:fs';
const require = createRequire(import.meta.url);
const { chromium } = require('C:/Users/ellio/AppData/Roaming/npm/node_modules/@playwright/mcp/node_modules/playwright');

const DIR = dirname(fileURLToPath(import.meta.url)).split('\\').join('/') + '/logo';
const browser = await chromium.launch({ channel: 'msedge', headless: true });

for (const f of readdirSync(DIR).filter(x => x.endsWith('.svg'))) {
  const svg = readFileSync(`${DIR}/${f}`, 'utf8');
  const w = Number(svg.match(/width="(\d+)"/)[1]);
  const h = Number(svg.match(/height="(\d+)"/)[1]);
  const page = await browser.newPage({ viewport: { width: w, height: h } });
  await page.setContent(
    `<style>html,body{margin:0;padding:0;background:transparent}svg{display:block}</style>${svg}`,
    { waitUntil: 'load' });
  await page.waitForTimeout(350);
  await page.screenshot({ path: `${DIR}/${f.replace('.svg', '.png')}`, omitBackground: true });
  console.log(`  ${f.replace('.svg', '.png')}  ${w}x${h}`);
  await page.close();
}
await browser.close();
