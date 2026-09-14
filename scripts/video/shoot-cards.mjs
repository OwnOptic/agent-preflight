import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';
import { readdirSync } from 'node:fs';
import { dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
const require = createRequire(import.meta.url);
const { chromium } = require('C:/Users/ellio/AppData/Roaming/npm/node_modules/@playwright/mcp/node_modules/playwright');

const DIR = dirname(fileURLToPath(import.meta.url)).split('\\').join('/') + '/cards';

const browser = await chromium.launch({ channel: 'msedge', headless: true });
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
for (const f of readdirSync(DIR).filter(x => x.endsWith('.html'))) {
  // Caption strips are 1920x132 and keep their transparency so ffmpeg can overlay them.
  const isStrip = f.startsWith('cap-');
  await page.setViewportSize({ width: 1920, height: isStrip ? 132 : 1080 });
  await page.goto(pathToFileURL(`${DIR}/${f}`).href);
  await page.waitForTimeout(700);
  await page.screenshot({ path: `${DIR}/${f.replace('.html', '.png')}`, omitBackground: isStrip });
  console.log('  ' + f.replace('.html', '.png'));
}
await browser.close();
