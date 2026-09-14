import { createRequire } from 'node:module';
import { pathToFileURL, fileURLToPath } from 'node:url';
import { dirname } from 'node:path';
import { readdirSync } from 'node:fs';
const require = createRequire(import.meta.url);
const { chromium } = require('C:/Users/ellio/AppData/Roaming/npm/node_modules/@playwright/mcp/node_modules/playwright');

const DIR = dirname(fileURLToPath(import.meta.url)).split('\\').join('/') + '/dossier-render';
const browser = await chromium.launch({ channel: 'msedge', headless: true });
const page = await browser.newPage({ viewport: { width: 1240, height: 1400 } });

for (const f of readdirSync(DIR).filter(x => x.endsWith('.html'))) {
  await page.goto(pathToFileURL(`${DIR}/${f}`).href, { waitUntil: 'load' });
  await page.waitForTimeout(500);
  const base = f.replace('.html', '');
  // The whole document, for reading.
  await page.screenshot({ path: `${DIR}/${base}-full.png`, fullPage: true });
  // The first screen, for a gallery card.
  await page.screenshot({ path: `${DIR}/${base}-top.png` });
  console.log('  ' + base);
}
await browser.close();
