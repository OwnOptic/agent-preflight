// Record the real pull request, its real failing check and the diff that caused it. The repository
// is public, so this is recorded signed out: what the camera sees is what anyone sees.
//
// Every navigation asserts on real content before the camera holds. GitHub served a 504 on one
// attempt, and a recording that holds for five seconds on a gateway error is worse than no shot.
import { createRequire } from 'node:module';
import { dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
const require = createRequire(import.meta.url);
const { chromium } = require('C:/Users/ellio/AppData/Roaming/npm/node_modules/@playwright/mcp/node_modules/playwright');

const HERE = dirname(fileURLToPath(import.meta.url)).split('\\').join('/');
const PR = 'https://github.com/OwnOptic/agent-preflight/pull/1';
const RUN = 'https://github.com/OwnOptic/agent-preflight/actions/runs/34820445553';

const browser = await chromium.launch({ channel: 'msedge', headless: true });
const ctx = await browser.newContext({
  viewport: { width: 1920, height: 1080 },
  recordVideo: { dir: HERE + '/raw-gh', size: { width: 1920, height: 1080 } },
});
const page = await ctx.newPage();

async function glide(px, ms = 1200) {
  const steps = Math.max(1, Math.round(ms / 40));
  for (let i = 0; i < steps; i++) {
    await page.mouse.wheel(0, px / steps);
    await page.waitForTimeout(40);
  }
}

// Load off camera until the page is genuinely there, then hold.
async function open(url, probe) {
  for (let attempt = 1; attempt <= 4; attempt++) {
    await page.goto(url, { waitUntil: 'domcontentloaded' });
    try {
      await page.locator(probe).first().waitFor({ state: 'visible', timeout: 12000 });
      return true;
    } catch {
      console.log(`  retry ${attempt}: ${url}`);
      await page.waitForTimeout(1500);
    }
  }
  throw new Error(`never rendered: ${url}`);
}

await open(PR, 'text=Update the records MCP manifest');
await page.waitForTimeout(4500);
await glide(900, 1200);
await page.waitForTimeout(5000);

// The check run itself. The pull request's Checks tab will not expand a log for a signed-out
// visitor, so go to the workflow run, which is public and shows the annotations outright.
await open(RUN, 'text=Update the records MCP manifest');
await page.waitForTimeout(6500);
await glide(500, 900);
await page.waitForTimeout(4000);

// The diff that caused it: an approved server rewrote one tool description.
await open(PR + '/files', 'text=mcp-tool-manifest.json');
await page.waitForTimeout(3000);
// The manifest is the second file in the diff, under the backlog edit.
await glide(1500, 1600);
await page.waitForTimeout(7000);

await ctx.close();
await browser.close();
console.log('done');
