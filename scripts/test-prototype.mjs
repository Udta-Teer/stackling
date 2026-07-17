/**
 * Stackling prototype smoke test — runs the REAL page in a REAL browser.
 *
 * This exists because simulating the renderer in Node kept confirming my own
 * assumptions instead of testing reality. Three shipped bugs prove the point:
 *   - `localStorage` at top level killed the whole script on file:// (the Node
 *     stub had no localStorage, so the simulation couldn't see it)
 *   - match_pairs keyed buttons by text, so duplicate TCP/UDP labels made half
 *     the column unreachable
 *   - .choice is display:flex, so any option containing a code span shattered
 *     into one column per fragment
 * Every one of those is visible in a browser in seconds and invisible to a stub.
 * A stub's querySelector returns a truthy fake — which is exactly how the
 * simulate renderer silently painted no numbers at all until this test ran.
 *
 * Setup (once):   npm install
 *                 npx playwright install chromium
 * Run:            npm test
 */
import { chromium } from 'playwright';

import { fileURLToPath, pathToFileURL } from 'node:url';
import { dirname, resolve } from 'node:path';
const FILE = pathToFileURL(
  resolve(dirname(fileURLToPath(import.meta.url)), '..', 'prototype', 'lesson.html')
).href;
let pass = 0, fail = 0;
const ok  = (m) => { pass++; console.log('  \x1b[32mPASS\x1b[0m ' + m); };
const bad = (m) => { fail++; console.log('  \x1b[31mFAIL\x1b[0m ' + m); };
const is  = (c, m) => c ? ok(m) : bad(m);

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 430, height: 900 } });  // iPhone-ish

const errors = [];
page.on('pageerror', e => errors.push(String(e)));
page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });

await page.goto(FILE + '#review');
await page.waitForTimeout(400);

// Drive the engine straight to a target. Top-level `let` bindings live in the
// global lexical scope, so evaluate() can reach them.
const jump = async (u, l, e) => {
  await page.goto(FILE + '#review');
  await page.waitForTimeout(250);
  await page.evaluate(([u,l,e]) => { uidx=u; UNIT=COURSE[u]; bootUnits(); boot(); startLesson(l); idx=e; render(); }, [u,l,e]);
  await page.waitForTimeout(200);
};


console.log('\n── page boots over file:// ──');
is(errors.length === 0, `no JS errors on load${errors.length ? ': ' + errors[0] : ''}`);
// Derived, not hardcoded: a tab count baked into the test rots every time a
// unit ships, and a rotting test teaches you to ignore failures.
const nUnits = await page.evaluate(() => COURSE.length);
is(await page.locator('#unittabs .utab').count() === nUnits, `all ${nUnits} unit tabs rendered`);

// The bug the user reported: options containing code spans shattered into columns.
console.log('\n── the reported bug: option B on unit 2 ──');
await jump(1, 3, 4);   // unit 2 / lesson 4 / the avatar exercise
const promptTxt = await page.locator('#stage .prompt').textContent();
is(promptTxt.includes('avatar'), 'reached the avatar exercise');
const bBox = await page.locator('#stage .choice').nth(1).boundingBox();
const bTxt  = await page.locator('#stage .choice').nth(1).locator('.txt').boundingBox();
const codes = await page.locator('#stage .choice').nth(1).locator('code').count();
is(codes === 3, `option B contains ${codes} code spans (the trigger)`);
is(bTxt.width > bBox.width * 0.7, `option B text spans ${Math.round(bTxt.width/bBox.width*100)}% of the button (was a narrow column)`);
is(bTxt.height < 130, `option B is ${Math.round(bTxt.height)}px tall, not a shattered stack`);
// no horizontal page scroll at phone width
const scrollW = await page.evaluate(() => document.documentElement.scrollWidth);
is(scrollW <= 430, `page does not scroll sideways at 430px (scrollWidth ${scrollW})`);

console.log('\n── concept card (unit 13, lesson 1) ──');
await jump(12, 0, 0);
is((await page.locator('#stage .kicker').textContent()) === 'Concept', 'first card is flagged as Concept');
is((await page.locator('.cbody').count()) === 1, 'concept body renders');
is((await page.locator('.viz .vn').count()) === 3, 'concept carries a 3-node diagram');
is((await page.locator('.viz .edges path[data-e]').count()) === 2, 'diagram draws 2 edges (excluding the arrowhead marker)');
is((await page.locator('#action').textContent()).trim() === 'Got it', 'action button says "Got it", not Check');
is(!(await page.locator('#action').isDisabled()), 'Got it is enabled immediately (no answer required)');
// nodes must not overlap — the layout is derived, so prove the geometry
const boxes = await page.locator('.viz .vn').evaluateAll(ns => ns.map(n => n.getBoundingClientRect()).map(r => ({x:r.x,y:r.y,w:r.width,h:r.height})));
let overlap = false;
for (let i = 0; i < boxes.length; i++) for (let j = i+1; j < boxes.length; j++) {
  const a = boxes[i], b = boxes[j];
  if (a.x < b.x+b.w && b.x < a.x+a.w && a.y < b.y+b.h && b.y < a.y+a.h) overlap = true;
}
is(!overlap, 'no two diagram nodes overlap');

console.log('\n── concept must not pollute the score ──');
await page.locator('#action').click();          // Got it
await page.waitForTimeout(150);
const heartsAfter = await page.locator('#hearts').textContent();
is(heartsAfter === '∞', 'review mode still on after concept card');

console.log('\n── simulate (unit 13, lesson 3) ──');
await jump(12, 2, 0);
is((await page.locator('input[type=range]').count()) === 1, 'simulate renders a slider');
const dbLoad = async () => (await page.locator('.vn[data-id="db"] .sub').textContent());
const melting = async () => (await page.locator('.vn[data-id="db"]').getAttribute('class')).includes('melt');
is((await dbLoad()).startsWith('20,000'), `at 0% hit rate all 20,000 req/s hits the db (${await dbLoad()})`);
is(await melting(), 'db is visibly melting at 0% hit rate');
await page.locator('input[type=range]').fill('50');
await page.waitForTimeout(80);
is((await dbLoad()).startsWith('10,000'), `at 50% → ${await dbLoad()} (halved)`);
is(await melting(), 'db still melting at 50%');
await page.locator('input[type=range]').fill('89');
await page.waitForTimeout(80);
is(await melting(), `at 89% → ${await dbLoad()}: still over the line`);
await page.locator('input[type=range]').fill('90');
await page.waitForTimeout(80);
is(!(await melting()), `at 90% → ${await dbLoad()}: survives (the knife edge)`);
await page.locator('input[type=range]').fill('99');
await page.waitForTimeout(80);
is((await dbLoad()).startsWith('200/'), `at 99% → ${await dbLoad()}: the 10× the lesson is about`);
// grade it
await page.locator('input[type=range]').fill('90');
await page.locator('#action').click();
await page.waitForTimeout(150);
is((await page.locator('.feedback').getAttribute('class')).includes('ok'), '90% grades as correct');

console.log('\n── build_diagram: real drag and drop (unit 13, lesson 2) ──');
await jump(12, 1, 5);   // the upgraded 2-hole diagram
is((await page.locator('.vn.hole').count()) === 2, 'the upgraded diagram has 2 holes (was 1)');
is((await page.locator('.chip.drag').count()) === 4, '4 draggable components (was 3)');
is(await page.locator('#action').isDisabled(), 'Check is disabled until every hole is filled');

// DRAG: Cache -> first hole. Real pointer events, not a click.
const drag = async (label, holeIdx) => {
  const chip = page.locator(`.chip[data-label="${label}"]`);
  const from = await chip.boundingBox();
  const to = await page.locator('.vn.hole').nth(holeIdx).boundingBox();
  await page.mouse.move(from.x + from.width/2, from.y + from.height/2);
  await page.mouse.down();
  await page.mouse.move(to.x + to.width/2, to.y + to.height/2, { steps: 12 });
  await page.waitForTimeout(60);
  const ghost = await page.locator('.chip.ghost').count();
  await page.mouse.up();
  await page.waitForTimeout(80);
  return ghost;
};
const ghostSeen = await drag('Cache', 0);
is(ghostSeen === 1, 'a drag ghost follows the pointer');
is((await page.locator('.chip.ghost').count()) === 0, 'ghost is cleaned up on drop');
is((await page.locator('.vn[data-id="h1"]').textContent()).includes('Cache'), 'Cache landed in the first hole');
is((await page.locator('.chip[data-label="Cache"]').getAttribute('class')).includes('used'), 'the used chip greys out');
is(await page.locator('#action').isDisabled(), 'Check still disabled with one hole left');
await drag('Database', 1);
is(!(await page.locator('#action').isDisabled()), 'Check enables once both holes are filled');
await page.locator('#action').click();
await page.waitForTimeout(150);
is((await page.locator('.feedback').getAttribute('class')).includes('ok'), 'Cache→Database grades correct');
is((await page.locator('.vn[data-id="h1"]').getAttribute('class')).includes('ok'), 'correct hole marked green');

console.log('\n── wrong order must fail (the ordering IS the lesson) ──');
await jump(12, 1, 5);   // the upgraded 2-hole diagram
await drag('Database', 0);
await drag('Cache', 1);
await page.locator('#action').click();
await page.waitForTimeout(150);
is((await page.locator('.feedback').getAttribute('class')).includes('bad'), 'Database→Cache grades WRONG (cache must come first)');

console.log('\n── legacy types still work ──');
await jump(0, 0, 0);
await page.locator('#stage .choice').first().click();
await page.locator('#action').click();
await page.waitForTimeout(120);
is((await page.locator('.feedback').count()) === 1, 'multiple_choice still grades');

console.log(`\n${errors.length ? '\x1b[31mJS errors: ' + errors.slice(0,3).join(' | ') + '\x1b[0m' : 'no JS errors across the whole run'}`);
console.log(`\n${pass} passed, ${fail} failed`);
await browser.close();
process.exit(fail ? 1 : 0);
