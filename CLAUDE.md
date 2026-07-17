# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

**Stackling** — a **Duolingo-style app that teaches system design**, beginner → advanced, through short gamified interactive lessons. Target platform is **mobile (React Native + Expo)**, but the app is not scaffolded yet — the repo is currently in the **content-authoring + prototype** phase. (Name locked 2026-07-16: *stack* + *-ling*; verified clear on App Store/Play + software trademark. Domain: grab `stackling.app` / `getstackling.com` — `stackling.com` is parked.)

## ⛔ Read these before doing anything

1. **`CONTENT_MASTER.md`** — the anchor doc and single source of truth for *what* we teach, *in what order*, *in what voice*, and *how far along we are*. **Every content-authoring session must start by reading it.** It exists to prevent scope-spiral: build **one concept at a time, top to bottom**, in the order of its build tracker (§6), and mark a concept ✅ before starting the next.
2. **`SPEC.md`** — product + technical design (exercise types, screens, tech stack, roadmap, content JSON schema).

## The hard rules (non-negotiable)

- **Content is DATA, not code.** Every lesson/exercise is JSON validated against a schema (`content/*.json`). Adding content = editing JSON, never touching components. This is the load-bearing architectural decision — preserve it.
- **Depth bar (owner directive):** the primary learner is a *basic coder who is NOT a system-design expert, building this to master the subject themselves*. Content must **start accessible but ramp to real depth and push hard** — the why, tradeoffs, failure modes, real numbers, "what breaks at scale." Never shallow. A unit that only tests recognition is unfinished. **Accuracy is on us — the learner cannot fact-check; be rigorous.** (Full rule: `CONTENT_MASTER.md` §1.)
- **Deliverables in HTML.** The owner wants tangible, clickable output — prefer self-contained HTML files (or Artifacts) over markdown/JSON docs. Keep the JSON content model as the source of truth regardless; HTML is a renderer/preview.

## Architecture: two renderers, one content model

```
content/*.json  ── the source of truth (lessons + exercises)
   │
   ├──►  prototype/lesson.html   the HTML preview renderer (built now, for feel/review)
   └──►  React Native / Expo app the real product renderer (built later)
```

- **`content/NN-<concept>.json`** — one file per concept/unit. A unit has `lessons[]`; each lesson has `exercises[]`; every exercise has a `type`, its type-specific answer fields, and a **`why`** (always — and the `why` carries all the depth). Optional `hint`. **⛔ `goDeeper` is retired everywhere — never write it**; the validator rejects it in any unit. Every stop-time review finding across units 8–11 landed in a `goDeeper` and none in a `why`; see `CONTENT_MASTER.md` §3.1. Content strings support inline markdown: `` `code` `` and `*emphasis*` — **mark up anything code-like** so learners can see it isn't prose (`CONTENT_MASTER.md` §3.2). Schema reference: `CONTENT_MASTER.md` §7.
- **`prototype/lesson.html`** — a self-contained, dependency-free HTML file that embeds unit JSON and renders the full lesson loop (progress bar, hearts, XP, per-type exercise renderers, instant feedback with the `why`, completion screen). It renders the legacy `goDeeper` box only when that field is present, so new units simply omit it — no renderer change needed. Its embedded `UNITn` objects mirror `content/*.json` — **when you author or change content, update the prototype's embedded copy too** so the two stay in sync until a loader replaces the manual embed. Verify with the source↔embed check (every prompt/choice/why in the JSON must appear verbatim in the HTML).

## Exercise types

Eleven types drive all content (defined in `SPEC.md` §3.2, usage guidance in `CONTENT_MASTER.md` §4): `multiple_choice`, `fill_blank`, `match_pairs`, `order_steps`, `multi_select`, `build_diagram`, `spot_bottleneck`, `tradeoff_slider`, `estimate`, **`concept`**, **`simulate`**. Each is JSON-driven and has a matching renderer in `prototype/lesson.html`. Adding a new type means: define its JSON shape in the spec **and** add a renderer + a `check()` branch in the prototype.

- **`concept`** — the only place we *teach* before testing. A claim-shaped `title`, an optional `viz`, a **hard-capped** `body` (360 chars) and optional `note` (220). Not graded: no `why`, no `answer`, no heart, no XP, and it never touches `total`, so it can't dilute accuracy. **The caps are load-bearing** — `goDeeper` died because an unbounded prose field is an invitation to ramble, and a concept card is the same shape. The validator enforces the cap and a max of 3 per lesson.
- **`simulate`** — the learner drags one variable and watches load flow through the topology until something melts. `sim.input` enters and flows down `sim.chain`; `sim.absorb` removes the share the learner controls; `sim.capacity` decides what turns red. The validator **recomputes the threshold from the model and rejects an `answerRange` that disagrees with it**, so the answer key cannot drift from the physics the learner sees.

## Diagrams: one engine, `viz`

Any exercise may carry a `viz` — `nodes` (each with an `id`, a `label` and a **`col`**) plus `edges` (`{from, to}`). Layout is *derived*, never authored: nodes sharing a column stack and centre, so a diagram can't drift from its data. `col` is the only layout input and it covers essentially every system diagram we teach. Fan-out is native — which is why the old string hacks (`'[ App Server ×3 ]'`, `'[ Posts svc, Users svc ]'`) are gone. Node `kind` (`client`/`lb`/`db`/`cache`/`queue`/…) picks the colour, so a component reads the same everywhere. Keep to **≤4 columns** or it scrolls sideways on a phone.

Nodes are HTML, not SVG `<text>` (SVG can't wrap, and labels go through `md()`); edges are an SVG layer underneath. **`.vn` is a flex container, so a label must always be wrapped in `.vl`** — `md()` output as a direct flex child shatters into one item per fragment. That's a real bug we shipped: see the `.choice .txt` comment.

## Commands

No build system yet (Expo app not scaffolded). Current workflow:

```bash
# Validate all content — RUN THIS AFTER EVERY CONTENT CHANGE. Exits 1 on failure.
python3 scripts/validate-content.py            # hard checks + advisory warnings
python3 scripts/validate-content.py --quiet    # hard checks only

# Regenerate the prototype's embedded content from content/*.json
python3 scripts/build-prototype.py             # write
python3 scripts/build-prototype.py --check     # exit 1 if the embed is stale

# Run the prototype in a REAL headless browser (setup: npm install && npx playwright install chromium)
npm test

npm run check   # build --check + validate + browser test, in one go

# Preview the lesson loop
open prototype/lesson.html          # macOS; any browser
open prototype/lesson.html#review   # unlimited hearts, for rapid content review
```

`npm test` is not optional politeness — every renderer bug we've shipped (the `file://` localStorage crash, match_pairs keyed by text, the flex-shatter, a simulate that painted no numbers at all) was invisible to a Node stub and obvious in a browser within seconds. A stub's `querySelector` returns a truthy fake; a browser doesn't. **Don't simulate the renderer in Node — run the page.**

`scripts/validate-content.py` is the real gate — don't hand-roll one-off checks instead of running it. Hard failures: invalid JSON, missing/empty `why`, out-of-range answer indices, missing type-specific fields, stray fields, **any `goDeeper` in units ≥12**, and source↔prototype-embed drift (it compares JSON-escaped, since the embed stores string literals). Advisory warnings (never fail; need human judgement): absolute technique claims with no in-sentence condition, and sentences naming one ACID property while asserting another's.

When the Expo app is scaffolded, add its `install / start / test / lint` commands here.

## Authoring workflow (per concept)

1. Read `CONTENT_MASTER.md`; take the next `⬜` concept in the §6 tracker (in order — don't jump ahead).
2. Author `content/NN-<concept>.json` following the lesson anatomy (hook → build → stretch → land), mixing 3–5 exercise types, ramping **easy → hard**, with a `why` on every exercise and depth as the default.
3. Mirror the new unit into `prototype/lesson.html` so it's playable.
4. Mark the concept ✅ in the `CONTENT_MASTER.md` tracker.

## Business context (affects content/product decisions)

- Pricing (recommended, under review): **$19/mo, $149/yr, 7-day free trial**. Positioning: "interview-grade system design, 10 minutes a day."
- **Launch at ~30% content** (Tiers 0–1 + Caching, Load balancing, Sharding, URL-shortener capstone ≈ 11 units), then keep shipping units.
- Offline-first through early milestones; backend/auth/payments are v2.
