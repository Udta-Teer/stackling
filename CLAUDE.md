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

- **`content/NN-<concept>.json`** — one file per concept/unit. A unit has `lessons[]`; each lesson has `exercises[]`; every exercise has a `type`, its type-specific answer fields, and a **`why`** (always — and the `why` carries all the depth). Optional `hint`. **⛔ `goDeeper` is retired from unit 12 onward — do not write it.** Every stop-time review finding across units 8–11 landed in a `goDeeper` and none in a `why`; see `CONTENT_MASTER.md` §3.1. It survives in units 1–11, which the owner is revisiting — don't retrofit those unless asked. Schema reference: `CONTENT_MASTER.md` §7.
- **`prototype/lesson.html`** — a self-contained, dependency-free HTML file that embeds unit JSON and renders the full lesson loop (progress bar, hearts, XP, per-type exercise renderers, instant feedback with the `why`, completion screen). It renders the legacy `goDeeper` box only when that field is present, so new units simply omit it — no renderer change needed. Its embedded `UNITn` objects mirror `content/*.json` — **when you author or change content, update the prototype's embedded copy too** so the two stay in sync until a loader replaces the manual embed. Verify with the source↔embed check (every prompt/choice/why in the JSON must appear verbatim in the HTML).

## Exercise types

Nine types drive all content (defined in `SPEC.md` §3.2, usage guidance in `CONTENT_MASTER.md` §4): `multiple_choice`, `fill_blank`, `match_pairs`, `order_steps`, `multi_select`, `build_diagram`, `spot_bottleneck`, `tradeoff_slider`, `estimate`. Each is JSON-driven and has a matching renderer in `prototype/lesson.html`. Adding a new type means: define its JSON shape in the spec **and** add a renderer + a `check()` branch in the prototype.

## Commands

No build system yet (Expo app not scaffolded). Current workflow:

```bash
# Validate all content — RUN THIS AFTER EVERY CONTENT CHANGE. Exits 1 on failure.
python3 scripts/validate-content.py            # hard checks + advisory warnings
python3 scripts/validate-content.py --quiet    # hard checks only

# Preview the lesson loop
open prototype/lesson.html      # macOS; just open the file in any browser
```

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
