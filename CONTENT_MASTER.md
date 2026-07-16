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
6. **Every exercise ends with a one-line `why`.** This is where learning locks in — treat it as the most important sentence in the lesson.
7. **No unexplained acronym, ever.** First use: spell it out, then abbreviate.
8. **Respect the reader's time.** If a sentence doesn't teach or delight, cut it.

---

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
| 5 | **Statelessness** | Servers that remember nothing per-request scale; where state actually lives |

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
| 3 | APIs | ⬜ | — |
| 4 | Latency vs throughput | ⬜ | — |
| 5 | Statelessness | ⬜ | — |
| 6 | What a database is | ⬜ | — |
| 7 | SQL vs NoSQL | ⬜ | — |
| 8 | Indexes | ⬜ | — |
| 9 | Transactions & ACID | ⬜ | — |
| 10 | Replication | ⬜ | — |
| 11 | Scaling: vertical vs horizontal | ⬜ | — |
| 12 | Load balancing | ⬜ | — |
| 13 | Caching | ⬜ | — |
| 14 | CDNs | ⬜ | — |
| 15 | Sharding / partitioning | ⬜ | — |
| 16 | Message queues & async | ⬜ | — |
| 17 | Rate limiting | ⬜ | — |
| 18 | CAP theorem | ⬜ | — |
| 19 | Consistency models | ⬜ | — |
| 20 | Consensus & leader election | ⬜ | — |
| 21 | Idempotency | ⬜ | — |
| 22 | Observability | ⬜ | — |
| 23 | Design a URL shortener | ⬜ | — |
| 24 | Design a news feed | ⬜ | — |
| 25 | Design a chat app | ⬜ | — |
| 26 | Design a rate limiter | ⬜ | — |
| 27 | Design a ride-sharing backend | ⬜ | — |

**Authoring order = the table order.** Do not jump ahead. Finish a concept (all lessons + `why` lines + a review pass) and mark it ✅ before starting the next.

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

Per-exercise required fields: `type`, `prompt`, the type-specific answer fields, and **`why`** (always). Optional: `goDeeper` (the mid-level nugget string), `hint`.

---

## 8. Business decisions locked here (so content reflects them)

- **Pricing (recommended):** $19/mo, $149/yr, 7-day free trial for all. *(Under review — see chat.)*
- **Launch strategy:** ship at ~30% content (Tiers 0–1 + key Tier 2 + URL shortener), keep shipping units.
- **Offline-first** through the early milestones; backend/sync is v2.
- **Positioning:** "Interview-grade system design, 10 minutes a day."
- **Product name (LOCKED 2026-07-16):** **Stackling** (*stack* + *-ling*). Verified clear on App Store/Play + software trademark; `stackling.com` parked, use `stackling.app`/`getstackling.com`. Brand system in `brand/brand-board.html`. **Mascot LOCKED:** the stacked-block "Stackling" — the logo *is* the mascot (amber top block = a big-faced head on two blue base layers). Emotions + animations to be added later to make it interactive/addictive. Prototype `prototype/lesson.html` is restyled to the full brand.
