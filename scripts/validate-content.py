#!/usr/bin/env python3
"""
Stackling content validator.

Hard checks (exit 1 on failure):
  - every content/*.json is valid JSON with the expected shape
  - every exercise has a non-empty `why`
  - answer indices are in range; type-specific fields are present
  - no stray/unknown fields
  - goDeeper is RETIRED for units >= GODEEPER_RETIRED_FROM (CONTENT_MASTER.md 3.1)
  - source <-> prototype embed: every prompt/choice/step/why in the JSON
    appears verbatim in prototype/lesson.html

Advisory warnings (never fail the build; require human judgement):
  - absolute claims about a technique with no condition in the same sentence
  - sentences naming one ACID property while asserting another's claim

Usage:
    python3 scripts/validate-content.py            # hard checks + warnings
    python3 scripts/validate-content.py --quiet    # hard checks only
"""

import json
import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTENT_GLOB = os.path.join(ROOT, "content", "*.json")
PROTOTYPE = os.path.join(ROOT, "prototype", "lesson.html")

# goDeeper is retired everywhere. See CONTENT_MASTER.md 3.1.
# It was removed from units 1-11 and never written for 12+; the `why` carries
# the depth. Nothing should reintroduce the field.
GODEEPER_RETIRED_FROM = 1

# A field task sends the learner OUT of the app. That's great for the one idea
# a terminal proves better than prose, and corrosive if it becomes a habit —
# every exit is a chance not to come back, and retention is the whole product.
# So the discipline is enforced here rather than left to judgement:
FIELD_TASK_MAX_TOTAL = 6      # across the entire course
FIELD_TASK_MAX_PER_UNIT = 1   # never two exits from one unit
FIELD_TASK_MAX_SECONDS = 60   # if it's longer, it's homework, not a side quest
FIELD_TASK_FIELDS = {"where", "seconds", "do", "alt", "notice"}
FIELD_TASK_REQUIRED = {"where", "seconds", "do", "notice"}
FIELD_TASK_WHERE = {"Terminal", "Browser"}  # must name where to run it

ALLOWED_FIELDS = {
    "id",  # stable per-exercise id: progress tracking + spaced repetition
    "type", "prompt", "choices", "answer", "why", "hint",
    "pairs", "steps", "slots", "palette", "nodes",
    "tolerance", "unit", "leftLabel", "rightLabel", "answerRange",
    "viz",                      # data-driven diagram: nodes + edges
    "title", "body", "note",    # concept card
    "sim",                      # simulate model
}

KNOWN_TYPES = {
    "multiple_choice", "fill_blank", "multi_select", "match_pairs",
    "order_steps", "build_diagram", "estimate", "tradeoff_slider",
    "spot_bottleneck", "concept", "simulate",
}

# A concept card is the ONLY place we teach before testing. It is also, exactly,
# the shape that killed goDeeper: an unbounded prose field. goDeeper was retired
# because every review finding in units 8-11 had landed in one — given room to
# ramble, the author rambles. So the cap is mechanical, not a guideline:
CONCEPT_BODY_MAX = 360        # ~55 words. One idea, stated once.
CONCEPT_NOTE_MAX = 220        # optional second beat, tighter still
CONCEPT_MAX_PER_LESSON = 3    # past this it's a textbook chapter, not a beat

# A diagram wider than this scrolls sideways on a phone, which is where this ships.
VIZ_MAX_COLS = 4
VIZ_NODE_FIELDS = {"id", "label", "col", "kind", "sub", "hole"}
VIZ_KINDS = {"client", "lb", "dns", "cdn", "gw", "server", "db",
             "cache", "queue", "storage"}

errors = []
warnings = []
seen_ids = set()
total_field_tasks = [0]
counts = {"concept": 0, "viz": 0}


def err(unit, lesson, msg):
    errors.append(f"{unit} :: {lesson} :: {msg}")


def warn(unit, lesson, msg):
    warnings.append(f"{unit} :: {lesson} :: {msg}")


def unit_number(path):
    base = os.path.basename(path)
    m = re.match(r"(\d+)", base)
    return int(m.group(1)) if m else None


def check_field_task(unit_name, lesson_id, t):
    """A field task must say WHERE to run the command — the whole point is that a
    learner who doesn't already know 'terminal vs browser' is the target reader."""
    stray = set(t) - FIELD_TASK_FIELDS
    if stray:
        err(unit_name, lesson_id, f"fieldTask stray field(s): {sorted(stray)}")
    missing = FIELD_TASK_REQUIRED - set(t)
    if missing:
        err(unit_name, lesson_id, f"fieldTask missing: {sorted(missing)}")
    if t.get("where") not in FIELD_TASK_WHERE:
        err(unit_name, lesson_id,
            f"fieldTask `where` must be one of {sorted(FIELD_TASK_WHERE)} "
            f"— got {t.get('where')!r}. A learner must be told where to run it.")
    secs = t.get("seconds")
    if not isinstance(secs, int) or not (0 < secs <= FIELD_TASK_MAX_SECONDS):
        err(unit_name, lesson_id,
            f"fieldTask `seconds` must be 1..{FIELD_TASK_MAX_SECONDS} — got {secs!r}")


def check_viz(unit_name, lesson_id, viz, who):
    """A diagram is data. Geometry is derived, so the only things worth checking
    are that the data is coherent: unique ids, edges pointing at real nodes, and
    a shape that still fits a phone screen."""
    nodes = viz.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        err(unit_name, lesson_id, f"{who}: viz needs a non-empty `nodes` list")
        return []
    ids = []
    for n in nodes:
        if not isinstance(n, dict):
            err(unit_name, lesson_id, f"{who}: every viz node must be an object")
            continue
        stray = set(n) - VIZ_NODE_FIELDS
        if stray:
            err(unit_name, lesson_id, f"{who}: viz node stray field(s): {sorted(stray)}")
        if not n.get("id"):
            err(unit_name, lesson_id, f"{who}: viz node missing `id`")
        else:
            ids.append(n["id"])
        if not n.get("hole") and not n.get("label"):
            err(unit_name, lesson_id, f"{who}: viz node {n.get('id')!r} needs a `label`")
        if n.get("kind") and n["kind"] not in VIZ_KINDS:
            err(unit_name, lesson_id,
                f"{who}: unknown viz kind {n['kind']!r} — one of {sorted(VIZ_KINDS)}")
        if "col" in n and not isinstance(n["col"], int):
            err(unit_name, lesson_id, f"{who}: viz node `col` must be an int")
    if len(set(ids)) != len(ids):
        err(unit_name, lesson_id, f"{who}: duplicate viz node id(s)")
    known = set(ids)
    for edge in viz.get("edges") or []:
        for end in ("from", "to"):
            if edge.get(end) not in known:
                err(unit_name, lesson_id,
                    f"{who}: edge `{end}` points at unknown node {edge.get(end)!r}")
    cols = {n.get("col", 0) for n in nodes if isinstance(n, dict)}
    if len(cols) > VIZ_MAX_COLS:
        warn(unit_name, lesson_id,
             f"{who}: {len(cols)} columns — over {VIZ_MAX_COLS} the diagram "
             f"scrolls sideways on a phone")
    return ids


def sim_load(sim, pct):
    """Mirror of simCompute() in the prototype: load enters at `input` and flows
    down `chain`; the absorb node removes pct% of what reaches it."""
    load, cur = {}, float(sim["input"])
    for nid in sim.get("chain") or []:
        load[nid] = cur
        if (sim.get("absorb") or {}).get("node") == nid:
            cur = cur * (1 - pct / 100.0)
    return load


def check_exercise(unit_no, unit_name, lesson_id, e):
    t = e.get("type")
    if t not in KNOWN_TYPES:
        err(unit_name, lesson_id, f"unknown exercise type: {t!r}")
        return

    stray = set(e) - ALLOWED_FIELDS
    if stray:
        err(unit_name, lesson_id, f"stray field(s): {sorted(stray)}")

    # A concept card teaches instead of grading, so `body` carries what `why`
    # carries elsewhere. Everything else must still explain itself.
    if t != "concept" and not e.get("why"):
        err(unit_name, lesson_id, "missing or empty `why`")

    # Every exercise needs a stable id — the app tracks progress by it, and
    # spaced repetition can't resurface what it can't name.
    eid = e.get("id")
    if not eid:
        err(unit_name, lesson_id, "missing `id`")
    elif eid in seen_ids:
        err(unit_name, lesson_id, f"duplicate exercise id: {eid!r}")
    else:
        seen_ids.add(eid)

    if unit_no is not None and unit_no >= GODEEPER_RETIRED_FROM and "goDeeper" in e:
        err(unit_name, lesson_id,
            f"`goDeeper` is retired from unit {GODEEPER_RETIRED_FROM} onward "
            f"(CONTENT_MASTER.md 3.1) — the `why` carries the depth")

    if t in ("multiple_choice", "fill_blank"):
        ch = e.get("choices")
        if not isinstance(ch, list) or len(ch) < 2:
            err(unit_name, lesson_id, "needs a `choices` list")
        elif not isinstance(e.get("answer"), int) or not (0 <= e["answer"] < len(ch)):
            err(unit_name, lesson_id, f"answer index out of range: {e.get('answer')}")
    elif t == "multi_select":
        ch = e.get("choices") or []
        ans = e.get("answer")
        if not isinstance(ans, list) or not ans:
            err(unit_name, lesson_id, "multi_select needs a non-empty answer list")
        elif not all(isinstance(i, int) and 0 <= i < len(ch) for i in ans):
            err(unit_name, lesson_id, f"multi_select answer index out of range: {ans}")
    elif t == "match_pairs":
        pairs = e.get("pairs")
        if not isinstance(pairs, list) or len(pairs) < 2:
            err(unit_name, lesson_id, "match_pairs needs >=2 pairs")
        elif not all("left" in p and "right" in p for p in pairs):
            err(unit_name, lesson_id, "every pair needs left+right")
    elif t == "order_steps":
        if not isinstance(e.get("steps"), list) or len(e["steps"]) < 2:
            err(unit_name, lesson_id, "order_steps needs >=2 steps")
    elif t == "concept":
        for k in ("title", "body"):
            if not e.get(k):
                err(unit_name, lesson_id, f"concept missing `{k}`")
        for k in ("answer", "choices", "hint"):
            if k in e:
                err(unit_name, lesson_id, f"concept is not graded — remove `{k}`")
        body = e.get("body") or ""
        if len(body) > CONCEPT_BODY_MAX:
            err(unit_name, lesson_id,
                f"concept `body` is {len(body)} chars, max {CONCEPT_BODY_MAX} — "
                f"a teaching beat, not a chapter (this cap is why goDeeper died)")
        note = e.get("note") or ""
        if len(note) > CONCEPT_NOTE_MAX:
            err(unit_name, lesson_id,
                f"concept `note` is {len(note)} chars, max {CONCEPT_NOTE_MAX}")
        title = (e.get("title") or "").strip()
        if title.endswith("?"):
            warn(unit_name, lesson_id,
                 "concept `title` is a question — it should assert the idea, "
                 "since this card is the one place we tell rather than ask")
        if e.get("viz"):
            check_viz(unit_name, lesson_id, e["viz"], "concept")
    elif t == "build_diagram":
        viz = e.get("viz")
        if not isinstance(viz, dict):
            err(unit_name, lesson_id, "build_diagram needs a `viz` (nodes + edges)")
            return
        check_viz(unit_name, lesson_id, viz, "build_diagram")
        holes = [n["id"] for n in viz.get("nodes") or []
                 if isinstance(n, dict) and n.get("hole") and n.get("id")]
        if not holes:
            err(unit_name, lesson_id, "build_diagram needs >=1 node with `hole: true`")
        pal = e.get("palette") or []
        ans = e.get("answer")
        if not isinstance(ans, dict):
            err(unit_name, lesson_id,
                "build_diagram `answer` must map holeId -> label (it grades a "
                "topology, not one chip)")
        else:
            if set(ans) != set(holes):
                err(unit_name, lesson_id,
                    f"answer keys {sorted(ans)} must match holes {sorted(holes)}")
            for h, lab in ans.items():
                if lab not in pal:
                    err(unit_name, lesson_id, f"answer for {h!r} not in palette: {lab!r}")
            if len(set(ans.values())) != len(ans):
                err(unit_name, lesson_id, "the same component fills two holes")
            # Without a distractor there is no decision to make.
            if len(pal) < len(holes) + 1:
                err(unit_name, lesson_id,
                    f"palette has {len(pal)} for {len(holes)} hole(s) — needs "
                    f"at least one wrong component to choose against")
    elif t == "simulate":
        viz = e.get("viz")
        sim = e.get("sim")
        if not isinstance(viz, dict) or not isinstance(sim, dict):
            err(unit_name, lesson_id, "simulate needs both `viz` and `sim`")
            return
        ids = set(check_viz(unit_name, lesson_id, viz, "simulate"))
        for k in ("input", "chain", "absorb", "watch"):
            if k not in sim:
                err(unit_name, lesson_id, f"simulate `sim` missing `{k}`")
                return
        for nid in sim["chain"]:
            if nid not in ids:
                err(unit_name, lesson_id, f"sim chain names unknown node {nid!r}")
        if sim["watch"] not in (sim.get("chain") or []):
            err(unit_name, lesson_id, f"sim `watch` {sim['watch']!r} is not in the chain")
        ab = sim.get("absorb") or {}
        for k in ("node", "label", "min", "max", "start"):
            if k not in ab:
                err(unit_name, lesson_id, f"sim `absorb` missing `{k}`")
                return
        if ab["node"] not in (sim.get("chain") or []):
            err(unit_name, lesson_id, f"sim `absorb.node` {ab['node']!r} is not in the chain")
        for nid in (sim.get("capacity") or {}):
            if nid not in ids:
                err(unit_name, lesson_id, f"sim capacity names unknown node {nid!r}")
        if "answerRange" not in e:
            err(unit_name, lesson_id, "simulate missing `answerRange`")
            return
        # The strong check: grade the graded answer against the model the
        # learner actually manipulates. If the content claims 90% is the
        # threshold and the simulation says 85%, the content is wrong — and
        # this is exactly the class of defect (a key disagreeing with reality)
        # that a human reviewer misses and arithmetic never does.
        cap = (sim.get("capacity") or {}).get(sim["watch"])
        rng = e["answerRange"]
        if cap is not None and isinstance(rng, list) and len(rng) == 2:
            ok = [p for p in range(int(ab["min"]), int(ab["max"]) + 1)
                  if sim_load(sim, p)[sim["watch"]] <= cap]
            if not ok:
                err(unit_name, lesson_id,
                    f"simulate is unwinnable: no setting gets {sim['watch']!r} "
                    f"under its capacity of {cap}")
            else:
                thresh = min(ok)
                if not (rng[0] <= thresh <= rng[1]):
                    err(unit_name, lesson_id,
                        f"answerRange {rng} does not contain the real threshold "
                        f"{thresh} — the simulation disagrees with the answer key")
    elif t == "spot_bottleneck":
        if e.get("viz"):
            ids = check_viz(unit_name, lesson_id, e["viz"], "spot_bottleneck")
            n = len(ids)
        else:
            nodes = e.get("nodes")
            if not isinstance(nodes, list) or len(nodes) < 2:
                err(unit_name, lesson_id, "spot_bottleneck needs a `nodes` list of >=2 (or a `viz`)")
                return
            n = len(nodes)
        if not isinstance(e.get("answer"), int) or not (0 <= e["answer"] < n):
            err(unit_name, lesson_id, f"spot_bottleneck answer index out of range: {e.get('answer')}")
    elif t == "estimate":
        for k in ("answer", "tolerance", "unit"):
            if k not in e:
                err(unit_name, lesson_id, f"estimate missing `{k}`")
    elif t == "tradeoff_slider":
        for k in ("answerRange", "leftLabel", "rightLabel"):
            if k not in e:
                err(unit_name, lesson_id, f"tradeoff_slider missing `{k}`")
        rng = e.get("answerRange")
        if isinstance(rng, list) and len(rng) == 2 and not (0 <= rng[0] < rng[1] <= 100):
            err(unit_name, lesson_id, f"answerRange not a valid 0-100 span: {rng}")


# ---------- advisory heuristics (warnings only) ----------

ABS = r"\bnever\b|\bwon't\b|\bwill not\b|\balways\b|\bonly ever\b|\bcannot\b"
TECH = (r"\bpin\w*|\brout\w*|\breplica\w*|\bfollower\w*|\bleader\b|\bcache\w*|"
        r"\bindex\w*|\bretry\b|\bmitigat\w*|\bthe fix\b|\bhealth check\w*")
COND = (r"\bif\b|\bunless\b|as long as|so long as|\bwhile\b|\buntil\b|\bprovided\b|"
        r"\bwhen\b|\bassuming\b|\bexcept\b|\bbut\b|\bmight\b|\bcan\b|\bmay\b|"
        r"\busually\b|\boften\b|\btend\w*|\balmost\b|\broughly\b|\bmostly\b")

ACID_NAME = {"atomicity": r"\batomic\w*",
             "durability": r"\bdurabilit\w*|\bdurable\b",
             "isolation": r"\bisolation\b"}
ACID_CLAIM = {
    "atomicity": r"all-or-nothing|all or nothing|as one unit|indivisible|half-done",
    "durability": r"\bpermanen\w*|\bsurviv\w*|\bpersist\w*|\bdurabl\w*",
    "isolation": r"\bvisibl\w*|\binvisibl\w*|\bcan see\b|dirty read|\bpeek\w*",
}


def advisory(unit_name, lesson_id, e):
    texts = [e.get("why") or "", e.get("goDeeper") or ""]
    if e["type"] in ("multiple_choice", "fill_blank") and isinstance(e.get("answer"), int):
        try:
            texts.append(e["choices"][e["answer"]])
        except (IndexError, KeyError, TypeError):
            pass
    elif e["type"] == "multi_select" and isinstance(e.get("answer"), list):
        texts += [e["choices"][i] for i in e["answer"] if i < len(e.get("choices") or [])]

    for txt in texts:
        for s in re.split(r"(?<=[.!?]) ", txt):
            if re.search(ABS, s, re.I) and re.search(TECH, s, re.I) and not re.search(COND, s, re.I):
                warn(unit_name, lesson_id, f"absolute technique claim, no in-sentence condition: {s.strip()[:100]}")
            named = [p for p, rx in ACID_NAME.items() if re.search(rx, s, re.I)]
            if len(named) == 1:
                foreign = [q for q, rx in ACID_CLAIM.items()
                           if q != named[0] and re.search(rx, s, re.I)]
                if foreign:
                    warn(unit_name, lesson_id,
                         f"names {named[0]} but asserts {foreign}: {s.strip()[:100]}")


def main():
    quiet = "--quiet" in sys.argv
    files = sorted(glob.glob(CONTENT_GLOB))
    if not files:
        print("FAIL: no content files found", file=sys.stderr)
        return 1

    try:
        html = open(PROTOTYPE, encoding="utf-8").read()
    except OSError as ex:
        print(f"FAIL: cannot read prototype: {ex}", file=sys.stderr)
        return 1

    total_lessons = total_ex = 0
    for f in files:
        name = os.path.basename(f)
        n = unit_number(f)
        try:
            d = json.load(open(f, encoding="utf-8"))
        except json.JSONDecodeError as ex:
            errors.append(f"{name} :: INVALID JSON :: {ex}")
            continue

        for key in ("unitId", "title", "lessons"):
            if key not in d:
                errors.append(f"{name} :: missing top-level `{key}`")

        unit_field_tasks = 0
        for lesson in d.get("lessons", []):
            lid = lesson.get("id", "<no id>")
            total_lessons += 1

            if lesson.get("fieldTask"):
                unit_field_tasks += 1
                total_field_tasks[0] += 1
                check_field_task(name, lid, lesson["fieldTask"])
        if unit_field_tasks > FIELD_TASK_MAX_PER_UNIT:
            errors.append(f"{name} :: {unit_field_tasks} field tasks — max "
                          f"{FIELD_TASK_MAX_PER_UNIT} per unit (each one is an exit "
                          f"from the app; don't stack them)")

        for lesson in d.get("lessons", []):
            lid = lesson.get("id", "<no id>")
            exs = lesson.get("exercises", [])

            n_concept = sum(1 for e in exs if e.get("type") == "concept")
            counts["concept"] += n_concept
            counts["viz"] += sum(1 for e in exs if e.get("viz"))
            if n_concept > CONCEPT_MAX_PER_LESSON:
                errors.append(f"{name} :: {lid} :: {n_concept} concept cards — max "
                              f"{CONCEPT_MAX_PER_LESSON} per lesson. Teaching beats are "
                              f"punctuation; past this the learner is reading, not playing.")
            if n_concept and all(e.get("type") == "concept" for e in exs):
                errors.append(f"{name} :: {lid} :: every card is a concept — a lesson "
                              f"that never asks anything is a slide deck")

            for e in exs:
                total_ex += 1
                check_exercise(n, name, lid, e)
                if not quiet:
                    advisory(name, lid, e)

                # source <-> embed drift.
                # The embed stores each string as a JSON string literal, so compare against
                # the escaped form — a raw compare false-positives on any content containing
                # a double quote (e.g. unit 3's '{"error": "user not found"}').
                fragments = [e.get("prompt", ""), e.get("why", ""),
                             e.get("title", ""), e.get("body", ""), e.get("note", "")]
                fragments += list(e.get("choices", []) or [])
                fragments += list(e.get("steps", []) or [])
                fragments += list(e.get("palette", []) or [])
                # Diagram text ships to the learner too, so it drifts like any other string.
                for node in (e.get("viz") or {}).get("nodes", []) or []:
                    fragments += [node.get("label", ""), node.get("sub", "")]
                for frag in fragments:
                    if frag and json.dumps(frag, ensure_ascii=False)[1:-1] not in html:
                        err(name, lid, f"NOT IN PROTOTYPE EMBED: {frag[:70]!r}")

    if total_field_tasks[0] > FIELD_TASK_MAX_TOTAL:
        errors.append(f"{total_field_tasks[0]} field tasks course-wide — max "
                      f"{FIELD_TASK_MAX_TOTAL}. Each one sends the learner out of "
                      f"the app; past a handful they stop being special and start "
                      f"costing retention.")

    print(f"content: {len(files)} units, {total_lessons} lessons, {total_ex} exercises")
    print(f"teaching: {counts['concept']} concept cards across {total_lessons} lessons "
          f"({counts['concept'] * 100 // max(1, total_lessons)}% covered)")
    print(f"visual:   {counts['viz']} exercises carry a diagram "
          f"({counts['viz'] * 100 // max(1, total_ex)}% of all exercises)")
    print(f"goDeeper retired from unit {GODEEPER_RETIRED_FROM} onward")
    print(f"field tasks: {total_field_tasks[0]}/{FIELD_TASK_MAX_TOTAL} "
          f"(1 per ~{total_lessons // max(1, total_field_tasks[0])} lessons)")

    if not quiet and warnings:
        print(f"\n{len(warnings)} advisory warning(s) — human judgement required:")
        for w in warnings:
            print(f"  ~ {w}")

    if errors:
        print(f"\nFAIL: {len(errors)} error(s):", file=sys.stderr)
        for e in errors:
            print(f"  x {e}", file=sys.stderr)
        return 1

    print("\nPASS: all hard checks green")
    return 0


if __name__ == "__main__":
    sys.exit(main())
