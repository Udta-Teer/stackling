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
// Address exercises by their stable id, never by position: inserting one
// concept card shifts every index in the lesson and silently retargets the test.
const jumpTo = async (exId) => {
  await page.goto(FILE + '#review');
  await page.waitForTimeout(250);
  const found = await page.evaluate((exId) => {
    for (let u = 0; u < COURSE.length; u++)
      for (let l = 0; l < COURSE[u].lessons.length; l++) {
        const i = COURSE[u].lessons[l].exercises.findIndex(e => e.id === exId);
        if (i >= 0) { uidx=u; UNIT=COURSE[u]; bootUnits(); boot(); startLesson(l); idx=i; render(); return true; }
      }
    return false;
  }, exId);
  await page.waitForTimeout(220);
  return found;
};


console.log('\n── page boots over file:// ──');
is(errors.length === 0, `no JS errors on load${errors.length ? ': ' + errors[0] : ''}`);
// Derived, not hardcoded: a tab count baked into the test rots every time a
// unit ships, and a rotting test teaches you to ignore failures.
const nUnits = await page.evaluate(() => COURSE.length);
is(await page.locator('#unittabs .utab').count() === nUnits, `all ${nUnits} unit tabs rendered`);

// The bug the user reported: options containing code spans shattered into columns.
console.log('\n── the reported bug: option B on unit 2 ──');
is(await jumpTo('csh-4-5'), 'found the avatar exercise by id');
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
await jumpTo('cache-1-0');
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
await jumpTo('cache-3-sim');
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
await jumpTo('cache-2-5');   // the upgraded 2-hole diagram
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
await jumpTo('cache-2-5');   // the upgraded 2-hole diagram
await drag('Database', 0);
await drag('Cache', 1);
await page.locator('#action').click();
await page.waitForTimeout(150);
is((await page.locator('.feedback').getAttribute('class')).includes('bad'), 'Database→Cache grades WRONG (cache must come first)');


console.log('\n── the ramp and the stairs: concept cards on/off ──');
await page.goto(FILE + '#review'); await page.waitForTimeout(250);
// default must be ON — the beginner never has to find a setting to be taught
is(await page.evaluate(()=>teach) === true, 'concept cards are ON by default');
await jumpTo('cache-1-0');
is((await page.locator('#stage .kicker').textContent()) === 'Concept', 'lesson opens on a concept card');
is((await page.locator('#cskip').count()) === 1, 'the card offers a one-tap way out');

// the stairs: one tap skips this card AND all future ones
await page.locator('#cskip').click();
await page.waitForTimeout(200);
is(await page.evaluate(()=>teach) === false, 'skip turns concept cards off');
is((await page.locator('#stage .kicker').textContent()) !== 'Concept', 'skip advanced past the card');
await page.evaluate(()=>{ uidx=12; UNIT=COURSE[12]; startLesson(1); });
await page.waitForTimeout(200);
is((await page.locator('#stage .kicker').textContent()) !== 'Concept',
   'a later lesson also opens straight on a question now');

// reversible from the header, or the toggle is a trap
await page.locator('#teachbtn').click(); await page.waitForTimeout(200);
is(await page.evaluate(()=>teach) === true, 'header toggle brings them back');
await page.evaluate(()=>{ uidx=12; UNIT=COURSE[12]; startLesson(1); });
await page.waitForTimeout(200);
is((await page.locator('#stage .kicker').textContent()) === 'Concept', 'teaching restored on the next lesson');

// the preference must survive a reload — that's what makes it a preference
await page.locator('#cskip').click(); await page.waitForTimeout(150);
await page.reload(); await page.waitForTimeout(400);
is(await page.evaluate(()=>teach) === false, 'the choice survives a reload');
is((await page.locator('#unittabs .utab').count()) > 0, 'and the page still boots (localStorage is guarded)');
await page.evaluate(()=>setTeach(true));

console.log('\n── counters count questions, not cards ──');
await jumpTo('cache-1-1');
const k = await page.locator('#stage .kicker').textContent();
is(/1\/\d+/.test(k), `first QUESTION reads as 1/n, not 2/n (got "${k}")`);


console.log('\n── match_pairs: a wrong connection must be undoable ──');
await jumpTo('csh-1-3');                       // 4 pairs, HTTP request anatomy
const L = () => page.locator('#stage .match .col').nth(0).locator('.chip');
const R = () => page.locator('#stage .match .col').nth(1).locator('.chip');
is(await L().count() === 4 && await R().count() === 4, 'renders 4 + 4 chips');
await L().nth(0).click(); await R().nth(0).click(); await page.waitForTimeout(80);
is((await L().nth(0).getAttribute('class')).includes('paired'), 'the pair marks as paired');
// the bug: a paired chip used to be pointer-events:none, so a wrong guess was permanent
is(await L().nth(0).isEnabled(), 'a paired chip is still clickable (was inert)');
const box = await L().nth(0).boundingBox();
is(box !== null && box.width > 0, 'and still hit-testable');
await L().nth(0).click(); await page.waitForTimeout(80);
is(!(await L().nth(0).getAttribute('class')).includes('paired'), 'tapping the left half breaks the pair');
is(!(await R().nth(0).getAttribute('class')).includes('paired'), 'and frees its right half too');
// break from the right-hand side as well
await L().nth(1).click(); await R().nth(1).click(); await page.waitForTimeout(60);
await R().nth(1).click(); await page.waitForTimeout(80);
is(!(await L().nth(1).getAttribute('class')).includes('paired'), 'tapping the right half also breaks it');
// completing all four still enables Check, and breaking one disables it again
for (let i = 0; i < 4; i++) { await L().nth(i).click(); await R().nth(i).click(); await page.waitForTimeout(30); }
is(!(await page.locator('#action').isDisabled()), 'Check enables when all four are paired');
await L().nth(2).click(); await page.waitForTimeout(80);
is(await page.locator('#action').isDisabled(), 'and disables again once a pair is broken');

console.log('\n── spot_bottleneck: colour must not answer the question ──');
await jumpTo('cp5-2-4');                       // Postgres is the only kind:"db" node AND the answer
const cls = await page.locator('#stage .vn').evaluateAll(ns => ns.map(n => n.className));
is(cls.length === 4, 'renders 4 nodes');
is(!cls.some(c => /\bk-/.test(c)), 'no node carries a kind colour — the odd one out was the answer');
const uniq = new Set(cls.map(c => c.replace(/\s*sel\s*/, '').trim()));
is(uniq.size === 1, `all nodes look identical until you read the numbers (${uniq.size} distinct style)`);


console.log('\n── match_pairs must reveal the correct pairing when you get it wrong ──');
await jumpTo('csh-1-3');
const LL = () => page.locator('#stage .match .col').nth(0).locator('.chip');
const RR = () => page.locator('#stage .match .col').nth(1).locator('.chip');
// answer it deliberately badly: pair everything in shuffled order
for (let i = 0; i < 4; i++) { await LL().nth(i).click(); await RR().nth(3-i).click(); await page.waitForTimeout(30); }
await page.locator('#action').click(); await page.waitForTimeout(200);
is((await page.locator('.feedback').getAttribute('class')).includes('bad'), 'a scrambled pairing grades wrong');
is((await page.locator('#stage .match.revealed').count()) === 1, 'the grid switches to the revealed answer');
is((await page.locator('#stage .mrow').count()) === 4, 'one row per correct pair');
const rowText = await page.locator('#stage .mrow').nth(0).textContent();
is(/→/.test(rowText), `each row shows left → right ("${rowText.trim().slice(0,44)}...")`);
is((await page.locator('#stage .myours').count()) > 0, 'and tells you what you said instead');
// the correct pairing must actually be on screen, not just a red box
const pairs = await page.evaluate(() => ex.pairs.map(p => p.right));
const shown = await page.locator('#stage .mrow .mr').allTextContents();
is(pairs.every(r => shown.some(s => s.trim() === r.replace(/[`*]/g,''))),
   'every correct answer is now visible on screen');

console.log('\n── a correct pairing reveals as all-green ──');
await jumpTo('csh-1-3');
const want = await page.evaluate(() => ex.pairs.map(p => p.right));
for (let i = 0; i < 4; i++) {
  await LL().nth(i).click();
  const rights = await RR().allTextContents();
  const j = rights.findIndex(t => t.trim() === want[i].replace(/[`*]/g,''));
  await RR().nth(j).click(); await page.waitForTimeout(30);
}
await page.locator('#action').click(); await page.waitForTimeout(200);
is((await page.locator('.feedback').getAttribute('class')).includes('ok'), 'correct pairing grades right');
is((await page.locator('#stage .mrow.ok').count()) === 4, 'all four rows green');
is((await page.locator('#stage .myours').count()) === 0, 'no "you said" line when nothing was wrong');

console.log('\n── checkpoints announce themselves ──');
await jumpTo('cp5-2-4');
is((await page.locator('#stage .kicker .cp').count()) === 1, 'a checkpoint lesson is badged Checkpoint');
await jumpTo('cache-1-1');
is((await page.locator('#stage .kicker .cp').count()) === 0, 'a normal lesson is not');
await page.goto(FILE + '#review'); await page.waitForTimeout(250);
await page.evaluate(() => { uidx=31; UNIT=COURSE[31]; bootUnits(); boot(); });
await page.waitForTimeout(150);
const sub = await page.locator('#pk-sub').textContent();
is(/Mixing units/.test(sub), `the picker explains why there's no lesson ("${sub.slice(0,40)}...")`);
await page.evaluate(() => { uidx=0; UNIT=COURSE[0]; bootUnits(); boot(); });
await page.waitForTimeout(150);
is(await page.locator('#pk-sub').isHidden() || (await page.locator('#pk-sub').textContent()) !== '',
   'units without a subtitle hide the line rather than leave a gap');

console.log('\n── build_diagram: a wrong drop must be undoable ──');
await jumpTo('cp5-2-2');
const dragTo = async (label, i) => {
  const c = await page.locator(`.chip[data-label="${label}"]`).boundingBox();
  const h = await page.locator('.vn.hole').nth(i).boundingBox();
  await page.mouse.move(c.x+c.width/2, c.y+c.height/2); await page.mouse.down();
  await page.mouse.move(h.x+h.width/2, h.y+h.height/2, {steps:10}); await page.mouse.up();
  await page.waitForTimeout(120);
};
await dragTo('Message Queue', 0);                  // deliberately wrong
is((await page.locator('.vn[data-id="h1"]').textContent()).includes('Message Queue'), 'a wrong component lands in the slot');
await page.locator('.vn[data-id="h1"]').click(); await page.waitForTimeout(150);
is((await page.locator('.vn[data-id="h1"]').textContent()).trim() === '?', 'tapping the filled slot clears it');
is(!(await page.locator('.chip[data-label="Message Queue"]').getAttribute('class')).includes('used'),
   'and the component returns to the palette');
// the undo existed all along — it was the HINT that never mentioned it
await dragTo('Cache', 0); await page.waitForTimeout(80);
is(/take it back/.test(await page.locator('.vhint').textContent()),
   'once a slot is filled, the hint says you can take it back');
await page.locator('.vn[data-id="h1"]').click(); await page.waitForTimeout(100);
is(/drag a component/.test(await page.locator('.vhint').textContent()),
   'and reverts once the slots are empty again');

console.log('\n── legacy types still work ──');
await jumpTo('hiw-1-1');
await page.locator('#stage .choice').first().click();
await page.locator('#action').click();
await page.waitForTimeout(120);
is((await page.locator('.feedback').count()) === 1, 'multiple_choice still grades');

console.log(`\n${errors.length ? '\x1b[31mJS errors: ' + errors.slice(0,3).join(' | ') + '\x1b[0m' : 'no JS errors across the whole run'}`);
console.log(`\n${pass} passed, ${fail} failed`);
await browser.close();
process.exit(fail ? 1 : 0);
