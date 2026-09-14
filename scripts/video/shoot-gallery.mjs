import { createRequire } from 'node:module';
import { pathToFileURL, fileURLToPath } from 'node:url';
import { dirname } from 'node:path';
import { readdirSync } from 'node:fs';
const require = createRequire(import.meta.url);
const { chromium } = require('C:/Users/ellio/AppData/Roaming/npm/node_modules/@playwright/mcp/node_modules/playwright');

const DIR = dirname(fileURLToPath(import.meta.url)).split('\\').join('/') + '/gallery';

const browser = await chromium.launch({ channel: 'msedge', headless: true });
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
for (const f of readdirSync(DIR).filter(x => x.endsWith('.html'))) {
  await page.goto(pathToFileURL(`${DIR}/${f}`).href);
  await page.waitForTimeout(700);
  await page.screenshot({ path: `${DIR}/${f.replace('.html', '.png')}` });
  console.log('  ' + f.replace('.html', '.png'));
}
await browser.close();
