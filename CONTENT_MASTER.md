# CONTENT MASTER — the anchor doc

> **Purpose:** This is the single source of truth for *what* we teach, *in what order*, *in what voice*, and *how far along we are*. Every content-authoring session starts by reading this file. It exists to stop scope-spiral: we build **one concept at a time, top to bottom**, and check it off here.

**Last updated:** 2026-07-16
**Owner:** content
**Related:** [SPEC.md](./SPEC.md) (product/tech), content files live in `/content`

---

## 0. The one-paragraph brief

We teach system design as a series of tiny, gamified lessons — beginner to advanced. A lesson takes 5 minutes and *always* teaches through interaction (tap, drag, order, estimate), never a wall of text. Content must delight a curious beginner **and** still hand a mid-level engineer something they didn't know. We launch at ~30% content built and keep shipping units as learners catch up.

---

## 1. Learner personas + THE HARD RULE

> **⛔ HARD RULE (owner's directive, non-negotiable):** The primary learner is **a basic coder who is NOT a system-design expert and is building this app to master the subject themselves.** Therefore content must **push them harder and go deep** — never shallow, never beginner-comfortable-and-done. Start accessible, then *ramp to real depth*: the why, the tradeoffs, the failure modes, the numbers, what breaks at scale. Every concept must leave them with something a senior engineer or interviewer would respect. Accuracy is entirely on us — the learner cannot fact-check. Still gamified and engaging, but **never dumbed down.**

Write for this arc within every unit:

- **Entry (accessible):** a basic coder with no system-design vocabulary. Analogies, concrete numbers, zero unexplained jargon. They must feel *smart*, not stupid.
- **Exit (deep + hard):** by the end of the unit they can reason about *why* a design is chosen, what its tradeoffs are, and how it fails at scale. Interview-grade.

**How to hit both:** open easy, then escalate hard inside the same unit. Depth is the **default**, not an optional "Go deeper" footnote — the nuggets now carry mechanisms, edge cases, and "why the obvious answer is wrong," and later lessons in a unit should genuinely challenge (multi-step reasoning, "what breaks," failure-mode diagnosis), not just recognition.

---

## 2. Voice & tone (non-negotiable rules)

1. **Concrete over abstract.** Never "improves performance" — say "cuts the response from 400ms to 20ms."
2. **Analogy first, term second.** Introduce the idea with a real-world analogy, *then* name it. ("A phonebook that turns names into numbers — that's DNS.")
3. **Numbers people can feel.** Use the "latency numbers every engineer should know," data sizes, request rates. Numbers make it real.
4. **War stories.** Sprinkle real incidents (the 2016 Dyn DNS outage, Twitter's fail whale, an S3 typo taking down half the web). These are the "Go deeper" candy.
5. **Short sentences. Warm, a little witty. Never smug.**
6. **Every exercise ends with a `why` — and the `why` carries all the depth.** This is where learning locks in; treat it as the most important text in the lesson. It must explain *why this specific answer is correct*, and deliver the mechanism, the tradeoff, the failure mode, or the real number in service of that. **Do not write `goDeeper` (see §3.1 — the field is retired from unit 12 onward).**
6b. **Attach conditions in-clause, never as a trailing caveat.** Write "X holds *while* Z", not "X holds." followed by "(but Z)". A claim and its limit belong in the same sentence, or the claim will be remembered without the limit.
6c. **Don't define a neighbouring concept.** Name it and point to its unit. Every unit owns its own definitions.
7. **No unexplained acronym, ever.** First use: spell it out, then abbreviate.
8. **Respect the reader's time.** If a sentence doesn't teach or delight, cut it.

---

### 3.1 ⛔ `goDeeper` is retired everywhere (decided 2026-07-16)

**Never emit a `goDeeper` field — omit it entirely (not `null`).** The `why` carries the depth instead. `scripts/validate-content.py` rejects the field in any unit, and the renderer no longer has a box for it.

**Why this changed:** every single stop-time review finding across units 8–11 (~12 of them) landed in a `goDeeper`; not one was in a `why`. The field's shape was the problem: a `why` is anchored — it must justify *this* answer — and that constraint keeps it honest. `goDeeper` was an open-ended aside, which is precisely where the writing drifted into defining neighbouring concepts, stating mitigations as guarantees, and repeating folklore as fact. Cutting the field removes the error surface rather than re-patching it.

*All 27 units were rewritten to fold that depth into the `why` (not concatenated — rewritten so each claim justifies its own answer).*

### 3.3 Field tasks — sending the learner outside the app

An optional `fieldTask` on a **lesson** sends the learner to their Terminal or browser to see one idea for real. It renders on the **lesson-complete screen only** — after the XP is banked — and is dismissible. It never appears mid-lesson and never blocks progress.

```jsonc
"fieldTask": {
  "where": "Terminal",              // REQUIRED. "Terminal" or "Browser" — nothing else.
  "seconds": 20,                    // REQUIRED. 1–60. Longer is homework, not a side quest.
  "do": "traceroute google.com",    // REQUIRED. The exact thing to do.
  "alt": "On Windows: `tracert …`", // optional: platform note / fallback
  "notice": "Every numbered line…"  // REQUIRED. What to look at, and why it's the lesson.
}
```

**⛔ Always say WHERE.** *"Run `traceroute google.com`"* is ambiguous to the exact learner this app is for — a basic coder may reasonably try the browser address bar. The `where` field is mandatory and validated against a closed set for precisely this reason.

**⛔ Use them sparingly — this is enforced, not advised.** Every field task is an exit from the app, and an exit is a chance not to come back; retention is the whole product. `scripts/validate-content.py` **fails the build** on: more than **6 course-wide**, more than **1 per unit**, a missing/invalid `where`, or `seconds` over 60.

**Only add one where doing the thing teaches something reading cannot** — hops you can count, a latency gap you can feel, a `304` you can watch. If prose conveys it just as well, don't spend an exit on it. Current: **3 of 6** (≈1 per 36 lessons).

### 3.2 Markdown in content strings

The renderer runs `md()` over **every** displayed string — prompts, choices, `why`, match pairs, steps, diagram nodes and palette, and slider labels. It supports:

| Syntax | Renders as | Use for |
|---|---|---|
| `` `code` `` | `<code>` — mono, blue, boxed | anything the learner would type or see in code: `GET /users/42`, `429 Too Many Requests`, `Cache-Control`, `SELECT *`, `COMMIT` |
| `*emphasis*` | `<em>` — italic, amber | the one word a sentence turns on |

**Mark up code so it looks like code.** A learner should be able to tell at a glance that `useEffect` is an identifier and not prose. HTML is escaped first, so `<script>` in content is safe.

**Don't** mark up bare numbers or ordinary words — `500 servers` is prose, `500 Internal Server Error` is code. Never regex-replace tokens in bulk: `/sec` in "requests/sec" and `/response` in "request/response" look exactly like paths to a pattern and are not.

## 3. Lesson anatomy (fixed template — don't reinvent per lesson)

Each **lesson** = 6–10 exercises, ~5 minutes, and follows this arc:

1. **Hook (1 exercise)** — a surprising fact or question that creates curiosity.
2. **Build (3–5 exercises)** — introduce the core idea in small steps, easiest interaction types first (`multiple_choice`, `fill_blank`, `match_pairs`), building to one active type (`order_steps`, `build_diagram`).
3. **Stretch (1–2 exercises)** — the mid-level "Go deeper" beat: a tradeoff, a real number, or an incident.
4. **Land (1 exercise)** — a synthesis/recall exercise that proves they got the core idea.

Difficulty within a unit ramps **easy → hard** (per the HARD RULE, §1 — don't stop at medium). New concepts go *recognition* (multiple choice) → *recall* (fill blank) → *application* (build/order) → **judgment & diagnosis** (tradeoff sliders, spot-the-bottleneck, "what breaks at scale," multi-step reasoning). Every unit must include at least one genuinely hard, make-them-think exercise near the end. A unit that only tests recognition is unfinished.

---

## 4. Exercise types (from SPEC §3.2) and when to use each

| Type | Use it for | Difficulty |
|------|-----------|-----------|
| `multiple_choice` | First contact with any idea | easy |
| `fill_blank` | Vocabulary lock-in | easy |
| `match_pairs` | Term ↔ definition, concept mapping | easy |
| `order_steps` | Lifecycles & data flows | medium |
| `multi_select` | "Which of these apply" nuance | medium |
| `build_diagram` | Composing an architecture | medium–hard |
| `spot_bottleneck` | Diagnosing scale problems | medium–hard |
| `tradeoff_slider` | Judgment calls with no single answer | hard |
| `estimate` | Back-of-envelope capacity math | hard |

**Rule:** a lesson uses **3–5 different types** to stay fresh. Never 8 multiple-choice in a row.

---

## 5. THE BIGGER PICTURE — full concept map

Ordered dependency-first. Each concept = one **unit** (3–5 lessons). Grouped into 5 tiers = the skill tree.

### Tier 0 — How things talk (Foundations)
| # | Concept | Core idea a beginner leaves with |
|---|---------|----------------------------------|
| 1 | **How the internet works** | The internet is computers passing packets; IP addresses + DNS + routers get them there |
| 2 | **Client–server & HTTP** | Your app asks (request), a server answers (response); status codes; methods |
| 3 | **APIs** | A contract for talking to a server; REST, JSON, endpoints |
| 4 | **Latency vs throughput** | Speed of one trip vs how many trips per second; the numbers to memorize |
| 5 | **Where state lives** | State is the hard part; the map of places state can live, source of truth vs copies, and how to decide *(re-scoped 2026-07-16 from "Statelessness" — that angle is already covered deeply in #2's boss lesson; this broader lens sets up caching, replication, and CAP)* |

### Tier 1 — Storing data (Databases)
| # | Concept | Core idea |
|---|---------|-----------|
| 6 | **What a database is** | Tables, rows, primary keys; why not just files |
| 7 | **SQL vs NoSQL** | Structured + relations vs flexible + scale; when each wins |
| 8 | **Indexes** | A book's index for your data; O(n) → O(log n); the write-cost tradeoff |
| 9 | **Transactions & ACID** | All-or-nothing operations; why banks need them |
| 10 | **Replication** | Copies of the DB; leader/follower; read scaling & failover |

### Tier 2 — Serving scale
| # | Concept | Core idea |
|---|---------|-----------|
| 11 | **Scaling: vertical vs horizontal** | Bigger machine vs more machines; why horizontal wins eventually |
| 12 | **Load balancing** | A traffic cop spreading requests; algorithms; health checks |
| 13 | **Caching** | Keep hot answers close; cache-aside; eviction; the hit-rate that matters |
| 14 | **CDNs** | Cache content near the user geographically; why static assets fly |
| 15 | **Sharding / partitioning** | Split one giant DB into pieces; shard keys; the hot-shard trap |
| 16 | **Message queues & async** | Decouple producer from consumer; buffer spikes; retries |
| 17 | **Rate limiting** | Protect a service from floods; token bucket; per-user limits |

### Tier 3 — Hard truths (Distributed systems)
| # | Concept | Core idea |
|---|---------|-----------|
| 18 | **CAP theorem** | Under a network split, pick consistency or availability |
| 19 | **Consistency models** | Strong vs eventual vs causal; what users actually feel |
| 20 | **Consensus & leader election** | How machines agree; quorums; a taste of Raft |
| 21 | **Idempotency** | Doing it twice = doing it once; safe retries |
| 22 | **Observability** | Logs, metrics, traces; you can't fix what you can't see |

### Tier 4 — Put it together (Design challenges / capstones)
| # | Concept | Core idea |
|---|---------|-----------|
| 23 | **Design a URL shortener** | Encoding, key generation, read-heavy caching — the "hello world" of design |
| 24 | **Design a news feed** | Fan-out on write vs read; the celebrity problem |
| 25 | **Design a chat app** | Websockets, delivery, presence, ordering |
| 26 | **Design a rate limiter** | Applies Tier 2 rate limiting at system scale |
| 27 | **Design a ride-sharing backend** | Geo, matching, real-time — the boss level |

> **Launch bar (~30%):** ship when **Tiers 0–1 + Caching, Load balancing, Sharding, and the URL-shortener capstone** are done. That's a coherent "beginner → first real design" journey (≈11 units). Everything after ships as updates.

---

## 6. Content build tracker

Status: `⬜ not started` · `🟨 drafting` · `✅ done` · `🔁 needs review`

| # | Concept | Status | File |
|---|---------|--------|------|
| 1 | How the internet works | ✅ done | `content/01-how-the-internet-works.json` |
| 2 | Client–server & HTTP | ✅ done | `content/02-client-server-http.json` |
| 3 | APIs | ✅ done | `content/03-apis.json` |
| 4 | Latency vs throughput | ✅ done | `content/04-latency-vs-throughput.json` |
| 5 | Where state lives *(re-scoped)* | ✅ done | `content/05-where-state-lives.json` |
| 6 | What a database is | ✅ done | `content/06-what-a-database-is.json` |
| 7 | SQL vs NoSQL | ✅ done | `content/07-sql-vs-nosql.json` |
| 8 | Indexes | ✅ done | `content/08-indexes.json` |
| 9 | Transactions & ACID | ✅ done | `content/09-transactions-and-acid.json` |
| 10 | Replication | ✅ done | `content/10-replication.json` |
| 11 | Scaling: vertical vs horizontal | ✅ done | `content/11-scaling-vertical-vs-horizontal.json` |
| 12 | Load balancing | ✅ done | `content/12-load-balancing.json` |
| 13 | Caching | ✅ done | `content/13-caching.json` |
| 14 | CDNs | ✅ done | `content/14-cdns.json` |
| 15 | Sharding / partitioning | ✅ done | `content/15-sharding.json` |
| 16 | Message queues & async | ✅ done | `content/16-message-queues.json` |
| 17 | Rate limiting | ✅ done | `content/17-rate-limiting.json` |
| 18 | CAP theorem | ✅ done | `content/18-cap-theorem.json` |
| 19 | Consistency models | ✅ done | `content/19-consistency-models.json` |
| 20 | Consensus & leader election | ✅ done | `content/20-consensus.json` |
| 21 | Idempotency | ✅ done | `content/21-idempotency.json` |
| 22 | Observability | ✅ done | `content/22-observability.json` |
| 23 | Design a URL shortener | ✅ done | `content/23-design-url-shortener.json` |
| 24 | Design a news feed | ✅ done | `content/24-design-news-feed.json` |
| 25 | Design a chat app | ✅ done | `content/25-design-chat-app.json` |
| 26 | Design a rate limiter | ✅ done | `content/26-design-rate-limiter.json` |
| 27 | Design a ride-sharing backend | ✅ done | `content/27-design-ride-sharing.json` |
| 28 | Checkpoint: Foundations (units 1–5) | ✅ done | `content/28-checkpoint-foundations.json` |
| 29 | Checkpoint: Storing Data (units 6–10) | ✅ done | `content/29-checkpoint-storing-data.json` |
| 30 | Checkpoint: Serving Scale (units 11–17) | ✅ done | `content/30-checkpoint-serving-scale.json` |
| 31 | Checkpoint: Hard Truths (units 18–22) | ✅ done | `content/31-checkpoint-hard-truths.json` |
| 32 | Checkpoint: Design Challenges (units 23–27) | ✅ done | `content/32-checkpoint-design-challenges.json` |

**Authoring order = the table order.** Do not jump ahead. Finish a concept (all lessons + `why` lines + a review pass) and mark it ✅ before starting the next.

### 6.1 Teaching cards — every lesson teaches before it tests

**⛔ THE RAMP PRINCIPLE (owner directive, 2026-07-17).** Every lesson opens with a `concept` card, and no argument from skip rates ever removes one.

The owner's words, and they overrule the reasoning that was here before:

> *"there are ramps in the building for wheelchairs, a very small fraction of people actually use them, in fact the majority of the people never use them still the buildings must have them."*

This corrected a real mistake in this doc. The earlier version argued against teaching content by citing "Duolingo's Tips page is the most-skipped surface in that app." **That reasoning is wrong and is recorded here so it doesn't get re-derived.** "Most people skip it" is a fact about the *majority's usage*; it was being used as a fact about the feature's *value*. The learner who is genuinely new cannot infer system design from exercises — language is pattern-inference, system design is not — and failing them is total, not proportional to their share. Skipping is what the *advanced* learner does, and their convenience is not a reason to fail the beginner.

**So: build both paths. Ramp and stairs. Nobody is asked to choose.**
- Teaching is ON by default. The beginner never has to find a setting to be taught.
- Every card carries a one-tap "I know this — skip concept cards", which kills this card *and all future ones*.
- Reversible any time from the header toggle, so trying it costs nothing.
- The preference persists (guarded `localStorage`, memory fallback on `file://`).

Rules that keep a card from becoming goDeeper 2.0:

- **The cap is the feature.** 360 chars for `body`, 220 for `note`, validator-enforced. `goDeeper` died because an unbounded prose field invites rambling; this is the same shape, so it gets a wall.
- **A claim, not a topic.** "A cache is a bet you'll be asked the same question twice", never "Caching". Never a question — that's what the exercises are for.
- **It must make the lesson's FIRST exercise answerable** by someone who arrived knowing nothing. That is the whole test of whether the card works.
- **Point of need.** The card sits at the head of the lesson whose exercises need it — not lumped into a front-loaded chapter.
- **Carry a `viz` where the idea has a shape.** Most system design ideas do. But a wrong diagram teaches a wrong mental model, so omit it rather than force one.
- **Don't define neighbouring concepts.** Each card does one job.
- **Max 3 per lesson**, and a lesson of only concept cards is rejected — it's a slide deck.

#### The card teaches the MECHANISM; the exercise supplies the INSTANCE

The failure mode a teaching card invites: teach so literally that the test becomes a memory check. Ask of every exercise — *could a learner get this right by recalling a sentence from the card, without reasoning?* If yes, the card spoiled it.

| | |
|---|---|
| ✅ **Healthy** — `rl-3-0` → `rl-3-1` | Card: a counter in one server's memory limits *per server*. Exercise: 10 servers × 1,000 rps — what's the real limit? The card never states 10,000. **The learner applies it.** |
| ❌ **Broken** — `rl-2-0` → `rl-2-1` | Card: *"100 requests at 10:00:59 plus 100 more at 10:01:00 is 200 in one second."* Exercise: exactly that, and the answer is that sentence. |

Spoiled means: the card states the answer (paraphrase counts); works the same example; enumerates all the correct options; names the distractor; or prints a number the learner is asked to compute.

**Not** spoiled: naming the concept (a caching card must say "cache"; a `fill_blank` answered "cache" is a vocabulary check), or making exercise 1 answerable — that's the card's *job*. Exercise 1 should be answerable by *reasoning from* the card, not by recalling a sentence in it.

Fix by moving the instance into the exercise and keeping the principle on the card; or by teaching on instance A and testing on instance B.

**`scripts/check-spoilers.py` catches only copy-paste, and its own docstring says so.** Calibrated against confirmed cases: `scale-4-0` → `scale-4-5` ("a complete pre-answer") scores **0%**, while the *healthy* `rl-3-0` → `rl-3-1` scores **25%**. The healthy card scores higher than the worst offender, because real spoilers are semantic. A clean run means "nobody copy-pasted" and nothing more — judging this needs a reader.

**Checkpoints (units 28–32) are the deliberate exception**: a checkpoint is a test *by design*, mixing units the learner has already been taught. No cards there.

### 6.2 Review status

All 32 units have now had an independent adversarial review (2026-07-17), including the checkpoints.

- **Units 1–11**: 23 fixes, then 6 more to repair defects those fixes introduced. The reviewer caught `txn-2-5` still contradicting the `txn-2-4` fix — the fix-two-of-three pattern.
- **All 108 concept cards**: 38 fixes. Real errors, e.g. `cons-3-0` taught that a leader removes the per-write majority (it doesn't — it amortizes the argument about *order*), `idx-4-0` defined selectivity inverted, `idx-2-0`'s B-tree diagram had one child per node.
- **Checkpoints 28–32**: first independent pass found a `spot_bottleneck` with a **tie** (two nodes at 5k, so the answer wasn't derivable) and three `why`s citing "Option 3" when the UI renders A–D.
- **De-spoiling pass**: all 108 cards rewritten so the card teaches the mechanism and the exercise supplies the instance. Verified: all 725 graded exercises byte-identical afterwards.

**The pattern to internalise: my own review finds ~zero; independent reviewers find many, every single time.** And my *fixes* introduce new errors at a steady rate — three in one batch, and the de-spoiling pass caught a fourth (a partial fix to `cm-3-0` had labelled "the like count went down" a read-your-writes symptom, contradicting `cm-3-6`'s key, which says it's monotonic reads). **Never ship a batch of fixes without an independent pass over the fixes themselves.**

---

## 7. Content JSON schema (authoring reference)

See `content/01-how-the-internet-works.json` for a worked example. Every unit file:

```jsonc
{
  "unitId": "how-internet-works",
  "tier": 0,
  "title": "How the Internet Works",
  "subtitle": "The internet is just computers passing notes",
  "objectives": ["...learner-facing 'by the end you can...' bullets..."],
  "lessons": [
    {
      "id": "hiw-1",
      "title": "...",
      "exercises": [ /* see SPEC §6.3 for per-type fields */ ]
    }
  ]
}
```

Per-exercise required fields: `type`, `prompt`, the type-specific answer fields, and **`why`** (always — and it carries the depth, see §3.1). Optional: `hint`. **`goDeeper` is retired — do not add it.** The validator rejects it in every unit; there are zero left in the course.

---

## 8. Business decisions locked here (so content reflects them)

- **Pricing (recommended):** $19/mo, $149/yr, 7-day free trial for all. *(Under review — see chat.)*
- **Launch strategy:** ship at ~30% content (Tiers 0–1 + key Tier 2 + URL shortener), keep shipping units.
- **Offline-first** through the early milestones; backend/sync is v2.
- **Positioning:** "Interview-grade system design, 10 minutes a day."
- **Product name (LOCKED 2026-07-16):** **Stackling** (*stack* + *-ling*). Verified clear on App Store/Play + software trademark; `stackling.com` parked, use `stackling.app`/`getstackling.com`. Brand system in `brand/brand-board.html`. **Mascot LOCKED:** the stacked-block "Stackling" — the logo *is* the mascot (amber top block = a big-faced head on two blue base layers). Emotions + animations to be added later to make it interactive/addictive. Prototype `prototype/lesson.html` is restyled to the full brand.
