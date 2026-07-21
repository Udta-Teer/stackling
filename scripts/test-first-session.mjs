import { chromium } from 'playwright';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { dirname, resolve } from 'node:path';

const file = pathToFileURL(resolve(dirname(fileURLToPath(import.meta.url)), '..', 'prototype', 'first-session.html')).href;
let pass = 0, fail = 0;
const check = (condition, message) => condition ? (pass++, console.log(`  PASS ${message}`)) : (fail++, console.error(`  FAIL ${message}`));
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
const errors = [];
page.on('pageerror', error => errors.push(String(error)));
page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
await page.goto(file);
await page.waitForTimeout(350);

check((await page.locator('#intro').textContent()).includes('90 requests/second'), 'traffic is explicit before the action');
check((await page.locator('#intro').textContent()).includes('60'), 'per-server capacity is explicit before the action');
check((await page.locator('#verdict').textContent()).includes('30'), 'initial queue growth is explicit');
check((await page.locator('#aLoad').textContent()).includes('90 in / 60 max'), 'Server A visibly receives all traffic');
check((await page.locator('#bLoad').textContent()).includes('0 in / 60 max'), 'Server B is visibly idle');
check((await page.locator('button').count()) === 1, 'the first step has exactly one action');
check((await page.locator('#action').textContent()) === 'Add a load balancer', 'the action names the architecture change');
check(await page.locator('#action').isVisible(), 'the action is visible without hunting');
const actionBox = await page.locator('#action').boundingBox();
check(actionBox.y < 844, 'the one action begins inside the first phone viewport');

await page.locator('#action').click();
await page.waitForTimeout(500);
check((await page.locator('#verdict').textContent()).includes('FIXED'), 'the action produces an explicit success verdict');
check((await page.locator('#aLoad').textContent()).includes('45 in / 60 max'), 'Server A receives 45 req/s afterward');
check((await page.locator('#bLoad').textContent()).includes('45 in / 60 max'), 'Server B receives 45 req/s afterward');
check((await page.locator('#verdict').textContent()).includes('All 90 req/s complete'), 'all 90 req/s complete');
check((await page.locator('#verdict').textContent()).includes('Queue: 0'), 'the queue visibly falls to zero');
check((await page.locator('#intro').textContent()).includes('45 requests/second to each server'), 'success copy replaces the obsolete direct-routing explanation');
check(await page.locator('.action').isHidden(), 'the completed action disappears instead of covering the result');
check((await page.locator('#why').textContent()).includes('did not create capacity'), 'the explanation prevents the load-balancer capacity misconception');
check(await page.locator('#continue').isVisible(), 'the success state has one clear path into the course');
check(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'no horizontal overflow at phone width');
check(errors.length === 0, `no browser errors${errors.length ? `: ${errors[0]}` : ''}`);

await browser.close();
console.log(`\n${pass} passed, ${fail} failed`);
if (fail) process.exit(1);
