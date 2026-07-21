# SysDesign — A Duolingo for System Design

**Version:** 0.1 (design spec)
**Platform:** Mobile-first, React Native + Expo (iOS & Android from one codebase)
**Status:** Pre-build design document

---

## 1. Product vision

Teach system design from absolute beginner to advanced through **short, gamified, interactive lessons** — the Duolingo model applied to distributed systems. Users build design intuition by *doing* (dragging components, spotting bottlenecks, making tradeoffs), not by reading.

**The core loop:**
> Open app → daily goal → 5-min lesson → instant feedback → earn XP → keep streak → concept resurfaces later (spaced repetition)

**Success metric (North Star):** number of lessons completed per weekly-active user. If people come back daily and finish lessons, the product works.

---

## 2. Who it's for

| Segment | Goal | Entry point |
|---------|------|-------------|
| Students / bootcamp grads | Learn fundamentals | Beginner path |
| Interview preppers | Practice design questions | "Design challenges" track |
| Working devs | Fill gaps, stay sharp | Skill tree by topic |

---

## 3. The learning experience

### 3.1 Structure (borrowed from Duolingo)

```
Course
└── Section        (e.g. "Foundations", "Scaling", "Real Systems")
    └── Unit        (e.g. "Caching")   ~4–6 lessons
        └── Lesson  (e.g. "Cache eviction")  ~5–10 exercises
            └── Exercise (one interaction)
```

- A **path** UI shows units as a vertical winding trail of nodes (locked → available → completed → gold/legendary).
- Finishing all lessons in a unit unlocks the next.
- A **checkpoint / unit review** every few units mixes previously-seen exercises (spaced repetition).

### 3.2 Exercise types

This is the product's differentiator. Each is a reusable component driven by JSON.

| # | Type | What the user does | Teaches |
|---|------|-------------------|---------|
| 1 | `multiple_choice` | Tap the right answer | Recall, tradeoffs |
| 2 | `multi_select` | Tap all that apply | Nuance ("which of these help with X") |
| 3 | `order_steps` | Drag steps into sequence | Request lifecycles, data flow |
| 4 | `build_diagram` | Drag components into slots | Architecture composition |
| 5 | `spot_bottleneck` | Tap the failing component in a diagram | Diagnosing scale problems |
| 6 | `tradeoff_slider` | Pick a position on a spectrum (e.g. consistency↔availability) | Judgment, no single right answer |
| 7 | `estimate` | Numeric input for capacity math | Back-of-envelope estimation |
| 8 | `fill_blank` | Choose word to complete a statement | Vocabulary |
| 9 | `match_pairs` | Match term ↔ definition | Concept mapping |
| 10 | `concept` | Read a concise mechanism-first explanation; optionally skip | Beginner access before assessment |
| 11 | `simulate` | Vary one input and watch load propagate through a system | Capacity intuition and thresholds |
| 12 | `system_change` | Apply one architecture change and compare explicit before/after topology and measurements | Causal system-design reasoning |

> **Build priority:** concept teaching and `system_change` are core lesson infrastructure. Recognition exercises support them; they are not the product's main event.

### 3.3 Feedback rules

- **Instant:** correct → green + ding + XP tick; wrong → red + gentle shake + short explanation.
- Every exercise carries a one-line **"why"** shown after answering — this is where real learning happens.
- Wrong answers cost a **heart**; running out ends the lesson early (or watch/wait to refill).

---

## 4. Curriculum outline

### Section 1 — Foundations (Beginner)
1. Client & server, requests/responses
2. Latency vs throughput
3. What a database does (tables, keys, indexes)
4. APIs & HTTP basics
5. Statelessness & why it matters

### Section 2 — Scaling (Intermediate)
6. Vertical vs horizontal scaling
7. Load balancing
8. Caching (where, what, eviction)
9. CDNs
10. Database replication
11. Sharding & partitioning
12. Message queues & async processing
13. Rate limiting

### Section 3 — Deep concepts (Advanced)
14. CAP theorem
15. Consistency models (strong, eventual, causal)
16. Consensus (leader election, quorums)
17. Idempotency & exactly-once
18. Observability (logs, metrics, traces)

### Section 4 — Design challenges (Applied, capstone)
19. Design a URL shortener
20. Design a news feed (Twitter)
21. Design a chat system
22. Design a ride-sharing backend
23. Design a rate limiter

Each challenge is a *guided* multi-exercise walk: requirements → estimation → high-level components → deep-dive on one piece → tradeoff review.

---

## 5. Gamification

| Mechanic | Rule |
|----------|------|
| **XP** | ~10 XP/exercise, bonus for perfect lessons |
| **Streak** | +1 per day a daily goal is met; freezes purchasable/earnable |
| **Hearts** | Start with 5; lose 1 per wrong answer; refill over time |
| **Daily goal** | User picks (Casual 1 lesson / Regular 2 / Serious 4) |
| **Leagues** | Weekly leaderboard bucketed into tiers, promotion/relegation |
| **Achievements** | "7-day streak", "First diagram", "Sharding master" |
| **Spaced repetition** | Missed concepts re-queued into review lessons |

Keep monetization out of v1. Design the schema so a future "hearts refill / streak freeze" store is easy, but don't build it yet.

---

## 6. Technical architecture

### 6.1 Stack

| Layer | Choice | Why |
|-------|--------|-----|
| App | **React Native + Expo (TypeScript)** | One codebase → iOS + Android; Expo = fast dev, OTA updates |
| Navigation | `expo-router` | File-based routing |
| State | **Zustand** | Tiny, simple for progress/session state |
| Local storage | `expo-sqlite` or `AsyncStorage` | Offline progress, works without login |
| Animations | `react-native-reanimated` + `gesture-handler` | Needed for drag exercises & feedback |
| Content | **JSON files bundled in-app** (v1) | No backend needed to start |
| Backend (v2) | Node + Postgres (or Supabase) | Auth, cloud sync, leagues |
| Analytics | PostHog / Amplitude | Track the learning loop |

### 6.2 Design principle: **content is data, not code**

Every lesson and exercise is JSON validated against a schema. Adding content = editing JSON, never touching components. This lets non-engineers author content and lets us iterate on curriculum fast.

### 6.3 Content schema (draft)

```jsonc
// A lesson
{
  "id": "caching-eviction",
  "unitId": "caching",
  "title": "Cache eviction",
  "exercises": [
    {
      "type": "multiple_choice",
      "prompt": "Your cache is full. Which policy evicts the least-recently-used item?",
      "choices": ["FIFO", "LRU", "Random", "TTL"],
      "answer": 1,
      "why": "LRU evicts the entry that hasn't been accessed for the longest time."
    },
    {
      "type": "order_steps",
      "prompt": "Order a cache-aside read.",
      "steps": [
        "Check cache",
        "On miss, read from DB",
        "Write value into cache",
        "Return value"
      ],
      "why": "Cache-aside: app checks cache first, falls back to DB, then populates."
    },
    {
      "type": "build_diagram",
      "prompt": "Place a cache to reduce DB read load.",
      "slots": ["Client", "?", "Database"],
      "palette": ["Cache", "Queue", "Load Balancer"],
      "answer": "Cache",
      "why": "A cache between app and DB absorbs repeated reads."
    }
  ]
}
```

```jsonc
// Skill-tree metadata
{
  "sections": [
    {
      "id": "foundations",
      "title": "Foundations",
      "units": [
        { "id": "client-server", "title": "Client & Server", "lessons": ["cs-1","cs-2"] },
        { "id": "databases", "title": "Databases", "lessons": ["db-1","db-2"] }
      ]
    }
  ]
}
```

### 6.4 App screens

1. **Home / Path** — winding trail of units, current position, streak + hearts + XP in header
2. **Lesson runner** — one exercise at a time, progress bar, feedback overlay, exit-confirm
3. **Lesson complete** — XP earned, accuracy, streak update
4. **Profile** — stats, achievements, streak calendar
5. **Leaderboard** — league standings (v2)
6. **Settings** — daily goal, notifications, sound

### 6.5 Data flow

```
JSON content (bundled) ──► Content loader ──► Lesson runner
                                                   │
User answers ──► Exercise component ──► Grader ──► XP/hearts update
                                                   │
                                          Progress store (Zustand + SQLite)
                                                   │
                                          (v2) Sync ──► Backend
```

---

## 7. Build roadmap

### Milestone 0 — Skeleton (½ day)
- Expo app boots, tab/stack navigation, design tokens (colors, spacing, typography)

### Milestone 1 — The loop (core!)
- Content JSON schema + loader + validator
- Lesson runner with progress bar & feedback overlay
- Exercise types: `multiple_choice`, `fill_blank`, `order_steps`, `match_pairs`
- One **real unit** ("Caching") authored end-to-end
- **Goal:** you can complete a lesson and it feels good

### Milestone 2 — Progression
- Skill-tree/path home screen with lock/unlock
- XP, hearts, daily streak (local, persisted)
- Lesson-complete screen

### Milestone 3 — The "wow" exercises
- `build_diagram` and `spot_bottleneck` (drag + tap on diagrams)
- `tradeoff_slider`, `estimate`

### Milestone 4 — Content scale-up
- Author Sections 1–2 fully
- Spaced-repetition review lessons

### Milestone 5 — Backend & social (v2)
- Auth, cloud progress sync
- Leagues/leaderboard
- Push notifications for streaks

---

## 8. Key risks & decisions

| Risk | Mitigation |
|------|-----------|
| System design answers aren't cleanly "right/wrong" | Use `tradeoff_slider` (accept a range) + explanations, not just MCQ |
| Content authoring is the real bottleneck | Invest early in a clean JSON schema + validator so content is cheap |
| Drag interactions are fiddly on mobile | Prototype `build_diagram` early; fall back to tap-to-place if drag is painful |
| Scope creep (leagues, store, social) | Ship the single-player loop first; everything social is v2 |

---

## 9. Open questions for you

1. **Content authorship** — will you write the curriculum content, or should the app include an authoring/preview tool?
2. **Depth of "design challenges"** — lightweight guided quizzes, or ambitious free-form diagram building?
3. **Monetization** — ever, or purely free/portfolio? (affects whether we build the hearts/store scaffolding)
4. **Backend timing** — okay to stay fully offline/local for the first several milestones?

---

*Next step: on your go-ahead, I'll scaffold the Expo project (Milestone 0) and build the lesson runner + first exercise types (Milestone 1) so you have a clickable "Caching" unit.*
