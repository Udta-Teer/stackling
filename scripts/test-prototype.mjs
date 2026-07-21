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
  // Fail HERE, naming the id. Returning silently meant a renamed exercise
  // surfaced 30 seconds later as a Playwright timeout on an unrelated selector.
  if (!found) { bad(`jumpTo: no exercise with id "${exId}" — did it get renamed?`); }
  return found;
};


console.log('\n── page boots over file:// ──');
is(errors.length === 0, `no JS errors on load${errors.length ? ': ' + errors[0] : ''}`);
// Derived, not hardcoded: a tab count baked into the test rots every time a
// unit ships, and a rotting test teaches you to ignore failures.
const nUnits = await page.evaluate(() => COURSE.length);
is(await page.locator('#unittabs .utab').count() === nUnits, `all ${nUnits} unit tabs rendered`);

console.log('\n── curriculum order follows prerequisites, not filenames ──');
const pathIds=await page.evaluate(()=>COURSE.map(u=>u.unitId));
const before=(a,b)=>pathIds.indexOf(a)>=0 && pathIds.indexOf(a)<pathIds.indexOf(b);
const follows=(checkpoint,prior)=>pathIds.indexOf(checkpoint)===pathIds.indexOf(prior)+1;
is(follows('checkpoint-foundations','where-state-lives'), 'Foundations checkpoint closes Foundations');
is(follows('checkpoint-storing-data','replication'), 'Data checkpoint closes Durable Data');
is(before('message-queues','idempotency'), 'queues create the retry problem before idempotency solves it');
is(follows('checkpoint-serving-scale','idempotency'), 'Serving Traffic checkpoint follows safe retries');
is(before('observability','resilience-backpressure'), 'learners see failures before learning to contain them');
is(before('consistency-models','cap-theorem') && before('cap-theorem','consensus'),
   'consistency vocabulary precedes CAP, which precedes consensus');
is(follows('checkpoint-hard-truths','disaster-recovery'), 'Distributed Systems checkpoint follows recovery');
is(before('authentication-authorization','security-threat-modeling'),
   'identity and authorization precede broader threat modeling');
is(before('multi-region-architecture','architecture-evolution'),
   'learners accumulate distributed costs before judging architecture evolution');
is(follows('checkpoint-design-challenges','architecture-evolution'),
   'Production Systems checkpoint closes the production stage');
is(pathIds.at(-1)==='design-ride-sharing', 'ride sharing remains the final design studio challenge');

console.log('\n── design studios teach complete paths and end in review ──');
const studioShape=await page.evaluate(()=>COURSE.filter(u=>u.unitId.startsWith('design-')).map(u=>({
  id:u.unitId, lessons:u.lessons.length, final:u.lessons.at(-1).title,
  types:[...new Set(u.lessons.at(-1).exercises.map(e=>e.type))]
})));
is(studioShape.length===8, 'all eight design studios are present');
for(const s of studioShape){
  is(s.lessons>=4 && /review/i.test(s.final), `${s.id} ends in a complete-system review`);
  is(['concept','system_change','build_diagram','multi_select'].every(t=>s.types.includes(t)),
     `${s.id} review teaches, breaks, rebuilds, and critiques the system`);
}
await jumpTo('urls-2-0');
is(/conditional insert/i.test(await page.locator('#stage .prompt').textContent()),
   'URL creation is taught as a conditional insert, not merely code generation');
is(await page.locator('#stage .vn').count()===4,
   'the creation card renders request, candidate, authoritative insert, and response');
await jumpTo('urls-2-create-flow');
is((await page.locator('#stage .flow-pool .chip').count())===5,
   'the learner builds all five steps of one-link creation');
console.log('\n── all 132 diagram-expansion drills render as real mobile interactions ──');
await page.setViewportSize({width:360,height:900});
const expansionAudit=await page.evaluate(()=>{
  const failures=[]; let count=0;
  for(let u=0;u<COURSE.length;u++) for(let l=0;l<COURSE[u].lessons.length;l++){
    const xs=COURSE[u].lessons[l].exercises;
    for(let i=0;i<xs.length;i++) if(xs[i].diagramExpansion===true){
      count++; uidx=u; UNIT=COURSE[u]; lidx=l; lesson=COURSE[u].lessons[l]; idx=i;
      render();
      const holes=document.querySelectorAll('#stage .vn.hole').length;
      const chips=document.querySelectorAll('#stage .chip').length;
      const expected=Object.keys(xs[i].answer||{}).length;
      if(holes!==expected || chips!==(xs[i].palette||[]).length)
        failures.push(`${xs[i].id}: holes ${holes}/${expected}, chips ${chips}/${(xs[i].palette||[]).length}`);
      if(document.documentElement.scrollWidth>innerWidth)
        failures.push(`${xs[i].id}: page width ${document.documentElement.scrollWidth}/${innerWidth}`);
    }
  }
  return {count,failures};
});
is(expansionAudit.count===132, `all ${expansionAudit.count} new drills reached the browser`);
is(expansionAudit.failures.length===0,
   `every new drill has complete slots/palette and stays inside 360px${expansionAudit.failures.length?': '+expansionAudit.failures.slice(0,3).join(' | '):''}`);

console.log('\n── every authored diagram state passes the mobile geometry and semantics gate ──');
const allDiagramAudit=await page.evaluate(()=>{
  const failures=[]; let states=0,edges=0,after=0;
  // 360px viewport -> 328px lesson content -> 302px inside the diagram frame.
  const root=document.createElement('div'); root.style.width='328px'; document.body.appendChild(root);
  for(const unit of COURSE) for(const lesson of unit.lessons) for(const exercise of lesson.exercises){
    for(const key of ['viz','afterViz']){
      const viz=exercise[key]; if(!viz)continue;
      states++; if(key==='afterViz')after++;
      root.innerHTML=''; const rendered=renderViz(viz); root.appendChild(rendered.wrap);
      const nodes=[...root.querySelectorAll('.vn')];
      const paths=[...root.querySelectorAll('.edges > path')]; edges+=paths.length;
      if(rendered.wrap.scrollWidth>rendered.wrap.clientWidth+1)
        failures.push(`${exercise.id}/${key}: frame scroll ${rendered.wrap.scrollWidth}/${rendered.wrap.clientWidth}`);
      if(paths.length!==(viz.edges||[]).length)
        failures.push(`${exercise.id}/${key}: edges ${paths.length}/${(viz.edges||[]).length}`);
      for(const n of nodes) if(n.scrollHeight>n.clientHeight+1 || n.scrollWidth>n.clientWidth+1)
        failures.push(`${exercise.id}/${key}: clipped ${n.dataset.id}`);
      for(let i=0;i<nodes.length;i++)for(let j=i+1;j<nodes.length;j++){
        const a=nodes[i].getBoundingClientRect(),b=nodes[j].getBoundingClientRect();
        if(a.left<b.right&&a.right>b.left&&a.top<b.bottom&&a.bottom>b.top)
          failures.push(`${exercise.id}/${key}: overlap ${nodes[i].dataset.id}/${nodes[j].dataset.id}`);
      }
      (viz.edges||[]).forEach((e,i)=>{
        if(!e.kind)failures.push(`${exercise.id}/${key}: edge ${i} has no kind`);
        if(['broken','blocked'].includes(e.kind)&&!e.label)
          failures.push(`${exercise.id}/${key}: ${e.kind} edge ${i} has no label`);
      });
    }
  }
  root.remove(); return {states,after,edges,failures};
});
is(allDiagramAudit.states===497, `all ${allDiagramAudit.states} before/after diagram states reached the renderer`);
is(allDiagramAudit.after===81, `all ${allDiagramAudit.after} changed-system states were included`);
is(allDiagramAudit.edges===1224, `all ${allDiagramAudit.edges} directed flows rendered`);
is(allDiagramAudit.failures.length===0,
   `no clipping, overlap, hidden scroll, missing edge, or unlabeled failure${allDiagramAudit.failures.length?': '+allDiagramAudit.failures.slice(0,4).join(' | '):''}`);

const connectionCount=await page.evaluate(()=>COURSE.flatMap(u=>u.lessons).flatMap(l=>l.exercises).filter(e=>e.connectEdges).length);
is(connectionCount===44, 'one diagram in every unit requires learner-authored connections');
const connectionExercise=await page.evaluate(()=>COURSE.flatMap(u=>u.lessons).flatMap(l=>l.exercises).find(e=>e.connectEdges).id);
await jumpTo(connectionExercise);
is(/Step 1 of 2/.test(await page.locator('.connect-panel').textContent()), 'connection exercise explicitly starts with component placement');
is(/Place all components/.test(await page.locator('#action').textContent()), 'disabled action explains what remains instead of only saying Check');
const connectionResult=await page.evaluate(()=>{
  const holes=[...document.querySelectorAll('#stage .vn.hole')];
  for(const hole of holes){
    const label=ex.answer[hole.dataset.id];
    const chip=[...document.querySelectorAll('#stage .chip')].find(c=>c.dataset.label===label);
    chip.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true})); hole.click();
  }
  for(const edge of ex.viz.edges){
    document.querySelector(`#stage .vn[data-id="${edge.from}"]`).click();
    document.querySelector(`#stage .vn[data-id="${edge.to}"]`).click();
  }
  return {connected:current.__edges?.size,required:ex.viz.edges.length,enabled:!document.querySelector('#action').disabled,
          visible:document.querySelectorAll('.edges > path.connected').length};
});
is(connectionResult.connected===connectionResult.required && connectionResult.enabled,
   `placing components is insufficient; connecting every required flow enables Check (${JSON.stringify(connectionResult)})`);
is(connectionResult.visible===connectionResult.required, `learner-authored connections appear on the diagram (${JSON.stringify(connectionResult)})`);
is(/System connected/.test(await page.locator('.connect-panel').textContent()), 'the interface confirms that connection work is complete');
is((await page.locator('#action').textContent())==='Check answer', 'Check becomes explicit when the answer is ready');
await page.setViewportSize({width:430,height:900});
await page.evaluate(() => exitToPicker());
await page.waitForTimeout(120);

console.log('\n── all 30 causal simulations expose a real model-checked threshold ──');
await page.setViewportSize({width:360,height:900});
const simulationAudit=await page.evaluate(()=>{
  const failures=[]; let count=0;
  for(let u=0;u<COURSE.length;u++) for(let l=0;l<COURSE[u].lessons.length;l++){
    const xs=COURSE[u].lessons[l].exercises;
    for(let i=0;i<xs.length;i++) if(xs[i].type==='simulate'){
      const sx=xs[i]; count++; uidx=u; UNIT=COURSE[u]; lidx=l; lesson=COURSE[u].lessons[l]; idx=i;
      render();
      const slider=document.querySelector('#stage input[type="range"]');
      const watch=document.querySelector(`#stage .vn[data-id="${sx.sim.watch}"]`);
      if(!slider||!watch){ failures.push(`${sx.id}: missing slider or watched node`); continue; }
      const safe=sx.answerRange[0]; slider.value=safe; slider.dispatchEvent(new Event('input',{bubbles:true}));
      if(watch.classList.contains('melt')) failures.push(`${sx.id}: answer ${safe} still melts`);
      if(safe>+slider.min){
        slider.value=safe-1; slider.dispatchEvent(new Event('input',{bubbles:true}));
        if(!watch.classList.contains('melt')) failures.push(`${sx.id}: ${safe-1} is also safe; threshold is not minimal`);
      }
      if(document.documentElement.scrollWidth>innerWidth)
        failures.push(`${sx.id}: page width ${document.documentElement.scrollWidth}/${innerWidth}`);
    }
  }
  return {count,failures};
});
is(simulationAudit.count===30, `all ${simulationAudit.count} simulations reached the browser`);
is(simulationAudit.failures.length===0,
   `every simulation has a visible minimal threshold at 360px${simulationAudit.failures.length?': '+simulationAudit.failures.slice(0,3).join(' | '):''}`);
await page.setViewportSize({width:430,height:900});
await page.evaluate(() => exitToPicker());
await page.waitForTimeout(120);

console.log('\n── every unit ends with an unfamiliar graded transfer problem ──');
await page.setViewportSize({width:360,height:900});
const transferAudit=await page.evaluate(()=>{
  const failures=[]; let count=0;
  for(let u=0;u<COURSE.length;u++){
    let unitCount=0;
    for(let l=0;l<COURSE[u].lessons.length;l++){
      const xs=COURSE[u].lessons[l].exercises;
      for(let i=0;i<xs.length;i++) if(xs[i].transfer===true){
        const sx=xs[i]; count++; unitCount++;
        uidx=u; UNIT=COURSE[u]; lidx=l; lesson=COURSE[u].lessons[l]; idx=i;
        checked=false; current=null; render();
        const choices=[...document.querySelectorAll('#stage .choice')];
        if(choices.length!==sx.choices.length){
          failures.push(`${sx.id}: choices ${choices.length}/${sx.choices.length}`);
          continue;
        }
        choices[sx.answer].click();
        check();
        if(!checked || !document.querySelector('#stage .choice.ok') || !document.querySelector('#feedback.feedback.ok'))
          failures.push(`${sx.id}: correct answer did not produce corrective feedback`);
        if(document.documentElement.scrollWidth>innerWidth)
          failures.push(`${sx.id}: page width ${document.documentElement.scrollWidth}/${innerWidth}`);
      }
    }
    if(unitCount!==1) failures.push(`${COURSE[u].unitId}: expected 1 transfer, found ${unitCount}`);
  }
  return {count,failures};
});
is(transferAudit.count===44, `all ${transferAudit.count} unit transfer problems reached the browser`);
is(transferAudit.failures.length===0,
   `every transfer problem renders and grades correctly at 360px${transferAudit.failures.length?': '+transferAudit.failures.slice(0,3).join(' | '):''}`);
await page.setViewportSize({width:430,height:900});
await page.evaluate(() => exitToPicker());
await page.waitForTimeout(120);

console.log('\n── selecting a lesson opens a focused lesson screen ──');
is(await page.locator('.top').isHidden(), 'lesson controls are hidden on the picker');
await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
await page.locator('#lessonpick .choice').last().click();
await page.waitForTimeout(180);
is(await page.locator('#picker').isHidden(), 'the lesson list disappears immediately');
is(!(await page.locator('#stage').isHidden()), 'the first lesson card/question is visible immediately');
is(!(await page.locator('.top').isHidden()), 'lesson controls appear only inside the lesson');
is(await page.evaluate(() => window.scrollY) === 0, 'the lesson opens at the top instead of inheriting picker scroll');
is(await page.evaluate(() => document.activeElement === document.querySelector('#stage')),
   'keyboard and assistive-technology focus moves into the lesson');
await page.locator('#closebtn').click();
await page.waitForTimeout(100);
is(!(await page.locator('#picker').isHidden()), 'Exit returns to the lesson picker');

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

console.log('\n── rate limiter: the bucket store decides; it does not proxy backend traffic ──');
is(await jumpTo('drl-2-5'), 'found the six-shard limiter exercise');
const limiterPrompt = await page.locator('#stage .prompt').textContent();
is(limiterPrompt.includes('500,000') && limiterPrompt.includes('100,000'),
   'the prompt supplies peak traffic and per-shard capacity');
is(limiterPrompt.includes('six-shard'), 'the required headroom and shard count are explicit');
const limiterEdges = await page.locator('.viz .edges path[data-e]').evaluateAll(ps => ps.map(p => p.getAttribute('d')));
const limiterModel = await page.evaluate(() => ex.viz.edges.map(e => `${e.from}->${e.to}${e.dash?' dashed':''}`));
is(limiterModel.includes('g->b dashed'), 'allowed backend work branches from the gateway');
is(!limiterModel.includes('h2->b'), 'the passive bucket cluster does not forward the API request');
is(limiterEdges.length === 3, 'the decision lookup and allowed request path both render');

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

console.log('\n── system_change: architecture action produces a measured consequence ──');
await jumpTo('state-change-1');
is((await page.locator('.change-status').textContent()).includes('cart disappears'), 'before measurement is visible');
is((await page.locator('#action').textContent()).includes('Move the cart'), 'action names the system change');
const beforeChangeNodes = await page.locator('.change-viz .vn').count();
await page.locator('#action').click();
await page.waitForTimeout(450);
is((await page.locator('.change-status').textContent()).includes('Server B reads'), 'after measurement replaces the failure state');
is((await page.locator('.change-status').getAttribute('class')).includes('after'), 'consequence is styled as a live success');
is((await page.locator('.change-viz .vn').count()) > beforeChangeNodes, 'topology visibly changes after the action');
is(/shared durable storage/i.test(await page.locator('.feedback').textContent()), 'mechanism explanation lands with the result');
is((await page.locator('#action').textContent()) === 'Continue', 'one action advances normally into the lesson');

console.log('\n── decision lab: wrong architecture changes are observable and revisable ──');
await jumpTo('state-change-2');
is((await page.locator('.change-options .choice').count()) === 3, 'lab presents three plausible architecture changes');
const labIdx = await page.evaluate(() => idx);
const labNodes = await page.locator('.change-viz .vn').count();
await page.locator('.change-options .choice').nth(0).click(); // sticky sessions: plausible, incomplete
is((await page.locator('.change-status').textContent()).includes('losing Server A'), 'wrong change explains the surviving failure');
is(await page.evaluate(() => idx) === labIdx, 'wrong change does not advance');
is((await page.locator('.change-viz .vn').count()) === labNodes, 'wrong change does not fake a repaired topology');
is(await page.locator('.change-options .choice').nth(2).isEnabled(), 'learner can revise the design');
await page.locator('.change-options .choice').nth(2).click();
is((await page.locator('.change-status').textContent()).includes('session loaded'), 'correct change produces the measured recovery');
is((await page.locator('.feedback').getAttribute('class')).includes('ok'), 'correct design reveals the causal explanation');
is((await page.locator('#action').textContent()) === 'Continue', 'successful lab rejoins the lesson loop');

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

console.log('\n── counters count interactions, not teaching cards ──');
await jumpTo('cache-change-1');
let k = await page.locator('#stage .kicker').textContent();
is(/1\/\d+/.test(k), `first interactive experiment reads as 1/n (got "${k}")`);
await jumpTo('cache-1-1');
k = await page.locator('#stage .kicker').textContent();
const expectedInteraction = await page.evaluate(() => {
  const exercises = UNIT.lessons[lidx].exercises.filter(ex => ex.type !== 'concept');
  return exercises.findIndex(ex => ex.id === 'cache-1-1') + 1;
});
is(new RegExp(`${expectedInteraction}\\/\\d+`).test(k),
  `the following quiz counts every interaction but no concept cards (got "${k}")`);


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
await jumpTo('cp1-2-3');                       // Four capacities; app servers at index 2 are the bottleneck
const cls = await page.locator('#stage .vn').evaluateAll(ns => ns.map(n => n.className));
is(cls.length === 4, 'renders 4 nodes');
is(!cls.some(c => /\bk-/.test(c)), 'no node carries a kind colour — the odd one out was the answer');
const uniq = new Set(cls.map(c => c.replace(/\s*sel\s*/, '').trim()));
is(uniq.size === 1, `all nodes look identical until you read the numbers (${uniq.size} distinct style)`);

// GRADE IT. The original version of this block stopped at the line above — it
// asserted how the nodes LOOKED and never pressed Check, so it stayed green
// while every spot_bottleneck threw a TypeError on grading and shipped broken.
// Appearance-only coverage on a graded type is not coverage.
const errsBefore = errors.length;
await page.locator('#stage .vn').nth(2).click();     // App servers = the answer
is(!(await page.locator('#action').isDisabled()), 'Check enables once a node is tapped');
await page.locator('#action').click();
await page.waitForTimeout(200);
is(errors.length === errsBefore, `Check does not throw${errors.length > errsBefore ? ': ' + errors[errsBefore] : ''}`);
is((await page.locator('.feedback').count()) === 1, 'feedback renders (the `why` reaches the learner)');
is((await page.locator('.feedback').getAttribute('class')).includes('ok'), 'tapping the constraint grades correct');
is((await page.locator('#stage .vn').nth(2).getAttribute('class')).includes('ok'), 'the answer node greens');
is((await page.locator('#action').textContent()).trim() !== 'Check', 'the button advances instead of staying stuck');

console.log('\n── a wrong bottleneck marks both nodes ──');
await jumpTo('cp1-2-3');
await page.locator('#stage .vn').nth(0).click();     // DNS = wrong
await page.locator('#action').click();
await page.waitForTimeout(200);
is((await page.locator('.feedback').getAttribute('class')).includes('bad'), 'a wrong tap grades wrong');
is((await page.locator('#stage .vn').nth(0).getAttribute('class')).includes('bad'), 'your wrong choice marks red');
is((await page.locator('#stage .vn').nth(2).getAttribute('class')).includes('ok'), 'and the correct one still greens');

console.log('\n── check() cannot be re-entered ──');
await jumpTo('cache-1-1');
await page.locator('#stage .choice').first().click();
await page.evaluate(() => { check(); check(); check(); });   // simulate the stuck-button storm
is(await page.evaluate(() => total) === 1, `three check() calls count as one attempt (total = ${await page.evaluate(() => total)})`);


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
await jumpTo('cp1-2-3');
is((await page.locator('#stage .kicker .cp').count()) === 1, 'a checkpoint lesson is badged Checkpoint');
await jumpTo('cache-1-1');
is((await page.locator('#stage .kicker .cp').count()) === 0, 'a normal lesson is not');
await page.goto(FILE + '#review'); await page.waitForTimeout(250);
await page.evaluate(() => {
  uidx=COURSE.findIndex(u=>u.unitId==='checkpoint-design-challenges');
  UNIT=COURSE[uidx]; bootUnits(); boot();
});
await page.waitForTimeout(150);
const sub = await page.locator('#pk-sub').textContent();
is(/Apply|Combine|Connect|Reason|Transfer/.test(sub), `the checkpoint subtitle explains the transfer task ("${sub.slice(0,40)}...")`);
await page.evaluate(() => { uidx=0; UNIT=COURSE[0]; bootUnits(); boot(); });
await page.waitForTimeout(150);
// Force the case rather than hoping a unit exhibits it: every unit has a
// subtitle today, so the previous `A || B` here short-circuited true and never
// tested anything. Proven by deleting the line it guards — still 102/102.
//
// exitToPicker() first, deliberately: page.goto() to a URL differing only by
// hash is a same-document navigation and does NOT reload, so the picker was
// still hidden from the previous jumpTo's startLesson() — and isHidden() is true
// when any ANCESTOR is hidden, which would have made this assert the wrong thing.
await page.evaluate(() => exitToPicker());
await page.evaluate(() => { UNIT = {...COURSE[0], subtitle: null}; boot(); });
await page.waitForTimeout(120);
is(await page.locator('#pk-sub').isHidden(), 'a unit with no subtitle hides the line rather than leaving a gap');
await page.evaluate(() => { UNIT = COURSE[0]; boot(); });
await page.waitForTimeout(120);
is(!(await page.locator('#pk-sub').isHidden()), 'and shows it again when there is one');

console.log('\n── build_diagram: a wrong drop must be undoable ──');
await jumpTo('cache-2-5');
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
is((await page.locator('.vn[data-id="h1"] .vl').textContent()).trim() === '?',
   'tapping the filled slot clears it while preserving the slot instruction');
is(!(await page.locator('.chip[data-label="Message Queue"]').getAttribute('class')).includes('used'),
   'and the component returns to the palette');
// the undo existed all along — it was the HINT that never mentioned it
await dragTo('Cache', 0); await page.waitForTimeout(80);
is(/take it back/.test(await page.locator('.vhint').textContent()),
   'once a slot is filled, the hint says you can take it back');
await page.locator('.vn[data-id="h1"]').click(); await page.waitForTimeout(100);
is(/drag a component/.test(await page.locator('.vhint').textContent()),
   'and reverts once the slots are empty again');


console.log('\n── EVERY graded type must survive Check (the net that was missing) ──');
// spot_bottleneck shipped throwing on every grade because the suite only ever
// asserted how it LOOKED. One broken type slipping through is a bug; a suite
// that can't notice is the actual defect. This walks every type in the course,
// answers one instance CORRECTLY by setting state directly, and presses Check.
// Any branch of check() that throws, or fails to produce feedback, fails here.
const typeReport = await page.evaluate(async () => {
  const seen = {}, out = [];
  for (let u = 0; u < COURSE.length; u++)
    for (let l = 0; l < COURSE[u].lessons.length; l++)
      for (let e = 0; e < COURSE[u].lessons[l].exercises.length; e++) {
        const t = COURSE[u].lessons[l].exercises[e].type;
        if (!seen[t]) seen[t] = [u, l, e];
      }
  for (const [t, [u, l, e]] of Object.entries(seen)) {
    if (t === 'concept') { out.push([t, 'ok', 'not graded']); continue; }
    // system_change is action-driven and has no Check state. Its causal
    // before→action→after contract is exercised by the dedicated E2E above.
    if (t === 'system_change') { out.push([t, 'ok', 'action-driven E2E']); continue; }
    try {
      uidx = u; UNIT = COURSE[u]; bootUnits(); boot(); startLesson(l); idx = e; render();
      const x = lesson.exercises[e];
      // Set the CORRECT answer directly — this exercises check(), not the widgets.
      if (t === 'multiple_choice' || t === 'fill_blank' || t === 'estimate' || t === 'spot_bottleneck') current = x.answer;
      else if (t === 'multi_select') current = new Set(x.answer);
      else if (t === 'order_steps') current = x.steps.map((s, i) => ({ s, i }));
      else if (t === 'build_diagram') current = { ...x.answer };
      else if (t === 'tradeoff_slider' || t === 'simulate') current = Math.round((x.answerRange[0] + x.answerRange[1]) / 2);
      else if (t === 'match_pairs') {
        const rights = current.rights;
        const map = {};
        x.pairs.forEach((p, i) => { map[i] = rights.indexOf(p.right); });
        current = { pending: null, map, rights };
      }
      check();
      const fed = document.querySelector('#feedback').className;
      out.push([t, /feedback/.test(fed) ? 'ok' : 'no-feedback', fed || '(empty)']);
    } catch (err) { out.push([t, 'THREW', String(err).split('\n')[0]]); }
  }
  return out;
});
for (const [t, status, detail] of typeReport) {
  is(status === 'ok', `${t.padEnd(16)} survives Check${status === 'ok' ? '' : ' → ' + status + ': ' + detail}`);
}
is(typeReport.length === 12, `all 12 exercise types covered (found ${typeReport.length})`);
// and correct answers must actually grade as correct, not merely not-throw
const graded = await page.evaluate(() => document.querySelector('#feedback').className);
is(/ok/.test(graded), 'the last correct answer graded as correct, not just silent');


console.log('\n── a stray second tap must not eat the `why` ──');
await jumpTo('hiw-1-1');
await page.locator('#stage .choice').first().click();
await page.locator('#action').click();                 // Check -> feedback
await page.waitForTimeout(30);
const idxAfterCheck = await page.evaluate(() => idx);
await page.locator('#action').click();                 // the stray second tap
await page.waitForTimeout(120);
is(await page.evaluate(() => idx) === idxAfterCheck, 'a fast second tap does not advance');
is((await page.locator('.feedback p').count()) === 1, 'the `why` is still on screen');
await page.waitForTimeout(420);                        // past the dead-time
await page.locator('#action').click();
await page.waitForTimeout(150);
is(await page.evaluate(() => idx) === idxAfterCheck + 1, 'a deliberate tap still advances');
// Check itself must NOT be dead-timed — answering fast is legitimate
await jumpTo('hiw-1-1');
await page.locator('#stage .choice').first().click();
await page.locator('#action').click();
await page.waitForTimeout(80);
is((await page.locator('.feedback p').count()) === 1, 'Check works immediately (no dead-time on Check)');

console.log('\n── a slider you never touched is not an answer ──');
await jumpTo('txn-4-6');
is(await page.locator('#action').isDisabled(), 'Check is disabled until the slider moves');
is(await page.evaluate(() => current) === null, 'current starts null, not 50');
await page.locator('#stage input[type=range]').fill('70');
await page.waitForTimeout(80);
is(!(await page.locator('#action').isDisabled()), 'moving it enables Check');

console.log('\n── estimate cannot brick Continue ──');
await jumpTo('lat-2-3');
await page.locator('#stage .est input').fill('500');
await page.locator('#action').click();
await page.waitForTimeout(150);
is((await page.locator('.feedback').count()) === 1, 'it grades');
is((await page.locator('#est-reveal').count()) === 1, 'and reveals the number');
const rev = await page.locator('#est-reveal').textContent();
is(/Answer:/.test(rev), `the answer is shown ("${rev.trim().slice(0,42)}...")`);
await page.locator('#stage .est input').fill('');       // the brick: clear after grading
await page.waitForTimeout(120);
is(!(await page.locator('#action').isDisabled()), 'clearing the field after grading does NOT kill Continue');

console.log('\n── order_steps reveals the sequence ──');
await page.setViewportSize({width:360,height:780});
await jumpTo('cache-2-1');
const flowCount = await page.evaluate(() => ex.steps.length);
is((await page.locator('.flow-slot').count()) === 1, 'mobile flow starts with one next-step slot, not a screen of empty boxes');
is(await page.evaluate(() => document.documentElement.scrollWidth === 360), 'flow builder has no horizontal overflow at 360px');
const initialFlowHeight = await page.locator('#body').evaluate(el => el.getBoundingClientRect().height);
is(initialFlowHeight < 560, `initial flow stays compact on a phone (${Math.round(initialFlowHeight)}px)`);
is((await page.locator('.order .arrows').count()) === 0, 'the old up/down list controls are gone');
is(await page.locator('#action').isDisabled(), 'Check waits until the complete flow is built');
await page.locator('.flow-pool .chip').first().click();
is((await page.locator('.order button.row').count()) === 1, 'tapping a candidate places a node into the flow');
is((await page.locator('.flow-slot').count()) === 2, 'the next slot appears progressively after the placed node');
await page.locator('.order button.row').first().click();
is((await page.locator('.order button.row').count()) === 0, 'tapping a placed node returns it for revision');
for(let i=0;i<flowCount;i++) await page.locator('.flow-pool .chip').first().click();
is(!(await page.locator('#action').isDisabled()), 'Check enables when the flow is complete');
await page.locator('#action').click();
await page.waitForTimeout(150);
is((await page.locator('#stage .order .row.ok, #stage .order .row.bad').count()) > 0, 'rows are marked after Check');
const shownOrder = await page.locator('#stage .order .lbl').allTextContents();
const trueOrder  = await page.evaluate(() => ex.steps.map(s => s.replace(/[`*]/g,'')));
is(JSON.stringify(shownOrder.map(t=>t.trim())) === JSON.stringify(trueOrder), 'the CORRECT sequence is displayed, in order');
await page.setViewportSize({width:430,height:900});

console.log('\n── losing is not winning ──');
await page.goto(FILE); await page.waitForTimeout(300);   // no #review -> hearts bite
await page.evaluate(() => { setTeach(false); uidx=0; UNIT=COURSE[0]; bootUnits(); boot(); startLesson(0); });
await page.waitForTimeout(200);
for (let i = 0; i < 8 && await page.evaluate(() => hearts) > 0; i++) {
  await page.evaluate(() => {
    // A WRONG answer must still be a WELL-FORMED one — `current = -999` for
    // every type just crashes match_pairs' grader and tests nothing.
    const x = lesson.exercises[idx], t = x.type;
    if (t === 'concept') { next(); return; }
    if (t === 'multiple_choice' || t === 'fill_blank' || t === 'spot_bottleneck')
      current = (x.answer + 1) % (x.choices ? x.choices.length : document.querySelectorAll('.vn.pick').length);
    else if (t === 'multi_select')
      current = new Set([[0,1,2,3].find(i => !x.answer.includes(i))].filter(v => v !== undefined));
    else if (t === 'order_steps')
      current = x.steps.map((s,i) => ({s, i})).reverse();
    else if (t === 'match_pairs') {
      const rights = current.rights, map = {};
      x.pairs.forEach((p,i) => { map[i] = (rights.indexOf(p.right) + 1) % rights.length; });
      current = { pending: null, map, rights };
    } else if (t === 'build_diagram') {
      const wrongLab = x.palette.find(l => !Object.values(x.answer).includes(l));
      current = {}; Object.keys(x.answer).forEach(h => { current[h] = wrongLab; });
    } else if (t === 'estimate') current = x.answer + (x.tolerance || 0) + 1e6;
    else if (t === 'tradeoff_slider' || t === 'simulate')
      current = x.answerRange[0] > 0 ? 0 : 100;
    check();
  });
  await page.waitForTimeout(60);
  await page.evaluate(() => { if (checked) next(); });
  await page.waitForTimeout(60);
}
is(await page.evaluate(() => hearts) === 0, 'ran out of hearts');
is((await page.locator('#done-title').textContent()) === 'Out of hearts', 'the screen says Out of hearts, not "Lesson complete!"');
is(!(await page.locator('#done-sub').isHidden()), 'and explains what to do next');
is(/again/i.test(await page.locator('#nextbtn').textContent()), 'the button offers a retry, not "Next lesson"');
is((await page.locator('.ftask').count()) === 0, 'no field task on a failed run — nothing was banked to reward');
// and the retry actually restarts the lesson with hearts back
await page.locator('#nextbtn').click();
await page.waitForTimeout(200);
is(await page.evaluate(() => hearts) === 5, 'the retry refills hearts');
// NOT `idx === 0`: teaching is off in this block, so startLesson correctly
// skips the concept card and lands on the first thing the learner SEES.
// `total` is the honest signal that the run reset.
is(await page.evaluate(() => total) === 0 && !(await page.locator('#stage').isHidden()),
   'and starts the run over with a clean slate');
await page.evaluate(() => setTeach(true));

console.log('\n── the ghost stage ──');
await page.goto(FILE + '#review'); await page.reload(); await page.waitForTimeout(350);
await page.locator('#lessonpick .choice').first().click();
await page.waitForTimeout(200);
await page.locator('#closebtn').click();                 // exit without answering
await page.waitForTimeout(150);
is(await page.evaluate(() => lesson === null), 'exiting drops the lesson');
// Picker mode deliberately hides lesson-only controls now. Exercise the same
// state change directly; it used to render a dead exercise over the picker.
await page.evaluate(() => setTeach(!teach));
await page.waitForTimeout(200);
is(await page.locator('#stage').isHidden(), 'the stage stays hidden — no exercise stapled over the picker');
is(!(await page.locator('#picker').isHidden()), 'the picker is still the picker');

console.log('\n── the arrowheads are solid, and coloured by state ──');
await jumpTo('cache-1-0');
const head = await page.evaluate(() => {
  const m = document.querySelector('marker#ah path'); const cs = getComputedStyle(m);
  return { fill: cs.fill, stroke: cs.stroke };
});
is(head.fill !== 'none', `arrowhead is filled, not hollow (${head.fill})`);
is(head.stroke === 'none', 'and not stroked by the edge rule');
is((await page.evaluate(() => document.querySelectorAll('.edges > path').length)) === 2,
   '".edges > path" selects only the 2 real edges, not the marker');
const markerGeometry = await page.evaluate(() => {
  const m=document.querySelector('marker#ah');
  return {refX:m.getAttribute('refX'), refY:m.getAttribute('refY'),
          units:m.getAttribute('markerUnits'), viewBox:m.getAttribute('viewBox')};
});
is(markerGeometry.refX === '9' && markerGeometry.refY === '5',
   'the arrow tip is the marker reference point, so it lands on the curve endpoint');
is(markerGeometry.units === 'userSpaceOnUse' && markerGeometry.viewBox === '0 0 10 10',
   'arrowhead size is stable across normal, live, and dead edge widths');

const endpoint = async locator => locator.evaluate(p => {
  const end=p.getPointAtLength(p.getTotalLength());
  const target=document.querySelector(`.vn[data-id="${p.dataset.to}"]`);
  return {x:end.x,y:end.y,dir:p.dataset.dir,left:target.offsetLeft,top:target.offsetTop,
          right:target.offsetLeft+target.offsetWidth,bottom:target.offsetTop+target.offsetHeight};
});
const landsOnTarget = g => g.dir === 'right' ? Math.abs(g.x-g.left)<.6 && g.y>=g.top && g.y<=g.bottom
  : g.dir === 'left' ? Math.abs(g.x-g.right)<.6 && g.y>=g.top && g.y<=g.bottom
  : g.dir === 'down' ? Math.abs(g.y-g.top)<.6 && g.x>=g.left && g.x<=g.right
  : g.dir === 'up' ? Math.abs(g.y-g.bottom)<.6 && g.x>=g.left && g.x<=g.right : false;
const forwardEnd=await endpoint(page.locator('.edges > path').first());
is(landsOnTarget(forwardEnd),
   `a forward curve terminates exactly on its target's left port (${forwardEnd.x.toFixed(1)}px)`);

console.log('\n── reverse and same-column edges use the correct ports ──');
await jumpTo('mig-1-0');
const reversePath=page.locator('.edges > path[data-from="n"][data-to="d"]');
is(await reversePath.count() === 1, 'the authored reverse edge is rendered');
const reverseEnd=await endpoint(reversePath);
is(reverseEnd.dir === 'left' && landsOnTarget(reverseEnd),
   'a reverse curve points left and terminates on the target\'s right port');
const vertical=await page.evaluate(() => edgePath({x:0,y:0},{x:0,y:90},102,56));
is(vertical.dir === 'down' && vertical.ty === 90 && vertical.tx === 51,
   'same-column nodes connect bottom-to-top instead of drawing a sideways loop');

console.log('\n── diagrams reach their own left edge on a small phone ──');
for (const W of [375, 360]) {
  const p2 = await browser.newPage({ viewport: { width: W, height: 900 } });
  await p2.goto(FILE + '#review'); await p2.waitForTimeout(300);
  await p2.evaluate(() => { for (let u=0;u<COURSE.length;u++) for (let l=0;l<COURSE[u].lessons.length;l++) {
    const i = COURSE[u].lessons[l].exercises.findIndex(e => e.id === 'cache-1-0');
    if (i>=0) { uidx=u; UNIT=COURSE[u]; bootUnits(); boot(); startLesson(l); idx=i; render(); return; } } });
  await p2.waitForTimeout(250);
  const geo = await p2.evaluate(() => {
    const wrap = document.querySelector('.vizwrap'), first = document.querySelector('.vn');
    return { wrapLeft: Math.round(wrap.getBoundingClientRect().left),
             firstLeft: Math.round(first.getBoundingClientRect().left) };
  });
  is(geo.firstLeft >= geo.wrapLeft - 1,
     `${W}px: the first node is reachable (starts at x=${geo.firstLeft}, container at x=${geo.wrapLeft})`);
  await p2.close();
}

console.log('\n── spot_bottleneck is answerable without a pointer ──');
await jumpTo('cp1-2-3');
await page.locator('#stage .vn').nth(2).focus();
await page.keyboard.press('Enter');
await page.waitForTimeout(80);
is(await page.evaluate(() => current) === 2, 'Enter on a focused node selects it');
is(!(await page.locator('#action').isDisabled()), 'and enables Check');

console.log('\n── legacy types still work ──');
await jumpTo('hiw-1-1');
await page.locator('#stage .choice').first().click();
await page.locator('#action').click();
await page.waitForTimeout(120);
is((await page.locator('.feedback').count()) === 1, 'multiple_choice still grades');

// ASSERT, don't print. This was a bare console.log: an injected uncaught
// TypeError showed up in red and the suite still exited 0, so `npm run check`
// went green over a broken page. Printing an error is not catching it.
is(errors.length === 0,
   `no JS errors across the whole run${errors.length ? ': ' + errors.slice(0,3).join(' | ') : ''}`);
console.log(`\n${pass} passed, ${fail} failed`);
await browser.close();
process.exit(fail ? 1 : 0);
