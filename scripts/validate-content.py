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
  - concept cards that use rhetorical contrast or mystery-box directions instead
    of directly explaining the mechanism

Usage:
    python3 scripts/validate-content.py            # hard checks + warnings
    python3 scripts/validate-content.py --quiet    # hard checks only
"""

import json
import glob
import math
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
    "actionLabel", "afterViz", "beforeStatus", "afterStatus", "result",
    "choiceFeedback",            # optional decision mode for system_change
    "diagramExpansion",          # course-wide 2026-07 diagram interaction pass
    "connectEdges",              # learner must connect placed diagram nodes
    "transfer",                  # unfamiliar application of an earlier mechanism
}

KNOWN_TYPES = {
    "multiple_choice", "fill_blank", "multi_select", "match_pairs",
    "order_steps", "build_diagram", "estimate", "tradeoff_slider",
    "spot_bottleneck", "concept", "simulate", "system_change",
}

# A concept card is the ONLY place we teach before testing. It is also, exactly,
# the shape that killed goDeeper: an unbounded prose field. goDeeper was retired
# because every review finding in units 8-11 had landed in one — given room to
# ramble, the author rambles. So the cap is mechanical, not a guideline:
CONCEPT_BODY_MAX = 360        # ~55 words. One idea, stated once.
CONCEPT_NOTE_MAX = 220        # optional second beat, tighter still
CONCEPT_MAX_PER_LESSON = 3    # past this it's a textbook chapter, not a beat

# Node size adapts down to 5 columns (see vizMetrics() in the prototype). Past
# that the text is too small to read, so it's a content problem, not a CSS one:
# a 6-stage diagram is two diagrams.
VIZ_MAX_COLS = 5
VIZ_NODE_FIELDS = {"id", "label", "col", "kind", "sub", "hole"}
VIZ_KINDS = {"client", "lb", "dns", "cdn", "gw", "server", "db",
             "cache", "queue", "storage"}
VIZ_EDGE_FIELDS = {"from", "to", "kind", "label", "count", "dash"}
VIZ_EDGE_KINDS = {"request", "data", "event", "replication", "invalidation",
                  "control", "optional", "broken", "blocked"}

errors = []
warnings = []
seen_ids = set()
total_field_tasks = [0]
counts = {"concept": 0, "viz": 0}


def err(unit, lesson, msg):
    errors.append(f"{unit} :: {lesson} :: {msg}")


def warn(unit, lesson, msg):
    warnings.append(f"{unit} :: {lesson} :: {msg}")


def check_semantic_landmines(unit_name, lesson_id, e):
    """Reject a few architecture/terminology errors that have already shipped.

    This is deliberately narrow. A regex cannot certify system-design accuracy,
    but it can stop a known false mental model from quietly returning after a
    later rewrite.
    """
    if e.get("type") == "match_pairs":
        for pair in e.get("pairs") or []:
            left, right = str(pair.get("left", "")), str(pair.get("right", ""))
            if re.search(r"\b(?:DELETE|PUT)\b", left, re.I) \
                    and re.search(r"\bsafe\b", right, re.I) \
                    and not re.search(r"\bnot safe\b", right, re.I):
                err(unit_name, lesson_id,
                    f"{left!r} is idempotent but not HTTP-safe; do not label it "
                    f"'safe' merely because repetition converges")
            if re.search(r"\bp99\b", left, re.I) and re.search(r"worst\s+1%", right, re.I):
                err(unit_name, lesson_id,
                    "p99 is a threshold at or below which 99% fall, not the set "
                    "of 'worst 1%' requests")

    if e.get("type") in {"concept", "build_diagram"} and isinstance(e.get("viz"), dict):
        title_prompt = f"{e.get('title', '')} {e.get('prompt', '')}".lower()
        labels = " ".join(str(n.get("label", "")) for n in e["viz"].get("nodes") or []).lower()
        labels += " " + " ".join(str(x) for x in (e.get("palette") or [])).lower()
        if "cache-first" in title_prompt and "cache" not in labels:
            err(unit_name, lesson_id,
                "claims a cache-first path but the diagram contains no cache")

    if e.get("type") == "build_diagram":
        prompt = e.get("prompt") or ""
        if re.search(r"\bshards?\b", prompt, re.I) and re.search(r"(?:req|checks?)/sec", prompt, re.I):
            if not re.search(r"(?:one|each|per)\s+(?:bucket\s+)?shard[^.]{0,80}(?:req|checks?)/sec", prompt, re.I):
                err(unit_name, lesson_id,
                    "asks the learner to size shards from a traffic rate without "
                    "stating per-shard capacity")

        # Infer labels for holes from the answer map, then catch the exact bad
        # topology that triggered this audit: a passive authority drawn as if it
        # forwards an application request to compute. Queues/logs/outboxes and
        # control-plane configuration stores are intentional exceptions.
        viz, answer = e.get("viz") or {}, e.get("answer") or {}
        node_label = {n.get("id"): n.get("label", "") for n in viz.get("nodes") or []}
        node_label.update(answer)
        passive = re.compile(r"\b(?:database|cache|redis|bucket shard|registry|state store)\b", re.I)
        active = re.compile(r"\b(?:backend|processor|worker|gateway|service)\b", re.I)
        exception = re.compile(r"\b(?:queue|log|outbox|discovery|config|version)\b", re.I)
        for edge in viz.get("edges") or []:
            source = str(node_label.get(edge.get("from"), ""))
            target = str(node_label.get(edge.get("to"), ""))
            if passive.search(source) and not exception.search(source) and active.search(target):
                err(unit_name, lesson_id,
                    f"diagram draws passive authority {source!r} forwarding to "
                    f"compute {target!r}; draw the caller's decision/request path")


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
        if not isinstance(edge, dict):
            err(unit_name, lesson_id, f"{who}: every viz edge must be an object")
            continue
        stray = set(edge) - VIZ_EDGE_FIELDS
        if stray:
            err(unit_name, lesson_id, f"{who}: viz edge stray field(s): {sorted(stray)}")
        for end in ("from", "to"):
            if edge.get(end) not in known:
                err(unit_name, lesson_id,
                    f"{who}: edge `{end}` points at unknown node {edge.get(end)!r}")
        if edge.get("kind") and edge["kind"] not in VIZ_EDGE_KINDS:
            err(unit_name, lesson_id,
                f"{who}: unknown edge kind {edge['kind']!r} — one of {sorted(VIZ_EDGE_KINDS)}")
        if "count" in edge and (not isinstance(edge["count"], int) or edge["count"] < 2):
            err(unit_name, lesson_id, f"{who}: edge `count` must be an integer >=2")
    cols = {n.get("col", 0) for n in nodes if isinstance(n, dict)}
    if len(cols) > VIZ_MAX_COLS:
        warn(unit_name, lesson_id,
             f"{who}: {len(cols)} columns — over {VIZ_MAX_COLS} the diagram "
             f"scrolls sideways on a phone")
    return ids


SLIDER_START = 50   # tradeoff_slider's neutral resting value — see slider() in the prototype


def check_answer_range(unit_name, lesson_id, e, minimum=0, maximum=100):
    """Validate an answerRange hard, and return it only if it's usable.

    The old checks were guarded by `isinstance(rng, list)`, so a NON-list
    silently skipped every one of them. That mattered: the prototype grades with
    `current >= ex.answerRange[0] && current <= ex.answerRange[1]`, and for the
    string "90" that indexes to "9" and "0" — so `90 >= "9" && 90 <= "0"` is
    always false. Every learner answer graded wrong, a heart lost each time, and
    the gate reported PASS. A type check that skips on the wrong type is not a
    type check.
    """
    rng = e.get("answerRange")
    if not isinstance(rng, list) or len(rng) != 2 or not all(isinstance(v, int) for v in rng):
        err(unit_name, lesson_id,
            f"answerRange must be a list of exactly 2 ints — got {rng!r} "
            f"({type(rng).__name__}). The renderer indexes it, so a string or a "
            f"float grades every answer wrong and says nothing.")
        return None
    if not (minimum <= rng[0] <= rng[1] <= maximum):
        err(unit_name, lesson_id,
            f"answerRange not within slider span {minimum}-{maximum}: {rng}")
        return None
    return rng


def embed_form(frag):
    """How a content string actually appears inside the generated embed.

    Mirrors build-prototype.py: JSON-escape, then `</` -> `<\\/` (the builder does
    that because a literal `</script>` in content would end the inline <script>
    and take the whole page down). If these two ever disagree, this check reports
    drift that isn't there — or misses drift that is.
    """
    return json.dumps(frag, ensure_ascii=False)[1:-1].replace("</", "<\\/")


def embed_fragments(e):
    """EVERY learner-facing string on an exercise. Add new fields here."""
    out = [e.get(k, "") for k in ("prompt", "why", "hint", "title", "body", "note",
                                  "unit", "leftLabel", "rightLabel")]
    out += list(e.get("choices") or [])
    out += list(e.get("choiceFeedback") or [])
    out += list(e.get("steps") or [])
    out += list(e.get("palette") or [])
    for p in e.get("pairs") or []:                      # the match_pairs answer key
        out += [p.get("left", ""), p.get("right", "")]
    for node in (e.get("viz") or {}).get("nodes", []) or []:
        out += [node.get("label", ""), node.get("sub", "")]
    for node in (e.get("afterViz") or {}).get("nodes", []) or []:
        out += [node.get("label", ""), node.get("sub", "")]
    out += [e.get(k, "") for k in ("actionLabel", "beforeStatus", "afterStatus", "result")]
    sim = e.get("sim") or {}
    out += [sim.get("inputLabel", ""), sim.get("watchLabel", "")]
    out += [(sim.get("absorb") or {}).get("label", "")]
    return [f for f in out if f]


def sim_state(sim, pct):
    """Mirror of simCompute() in the prototype: load enters at `input` and flows
    down `chain`; the absorb node removes pct% of what reaches it.

    Rounds at each hop exactly as the prototype does — if these two ever
    disagree, this check silently validates a model the learner never sees.
    """
    model = sim.get("model") or {"kind": "flow"}
    kind = model.get("kind", "flow")
    capacity = dict(sim.get("capacity") or {})
    if kind == "queue":
        service = pct * model["servicePerUnit"]
        backlog = max(0, math.floor((sim["input"] - service) * model["duration"] + 0.5))
        load = {nid: sim["input"] for nid in sim.get("chain") or []}
        load[sim["watch"]] = backlog
        return load, capacity
    if kind == "retry":
        total = math.floor(sim["input"] * (1 + model["retryFraction"] * (1 - pct / 100.0)) + 0.5)
        return {nid: total for nid in sim.get("chain") or []}, capacity
    if kind == "pool":
        load = {nid: sim["input"] for nid in sim.get("chain") or []}
        capacity[sim["watch"]] = pct * model["servicePerUnit"]
        return load, capacity
    load, cur = {}, float(sim["input"])
    for nid in sim.get("chain") or []:
        load[nid] = cur
        if (sim.get("absorb") or {}).get("node") == nid:
            # floor(x+0.5), NOT round(): Python rounds half to even (round(2.5)==2)
            # and JS Math.round rounds half up (3). Same spelling, different answer.
            cur = math.floor(cur * (1 - pct / 100.0) + 0.5)
    return load, capacity


def sim_load(sim, pct):
    return sim_state(sim, pct)[0]


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

    check_semantic_landmines(unit_name, lesson_id, e)

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
        # The renderer keys its chip lookup table by label. Duplicate labels would
        # collapse to one entry, so only the last chip would grey out and the
        # "used once" sweep would clear the wrong hole. Keying by text has now
        # shipped as a bug twice (match_pairs, then this table), so gate it.
        if len(set(pal)) != len(pal):
            dupes = sorted({l for l in pal if pal.count(l) > 1})
            err(unit_name, lesson_id,
                f"palette has duplicate label(s) {dupes} — the renderer keys chips "
                f"by label, so duplicates collapse into one and misbehave")
            # Without a distractor there is no decision to make.
            if len(pal) < len(holes) + 1:
                err(unit_name, lesson_id,
                    f"palette has {len(pal)} for {len(holes)} hole(s) — needs "
                    f"at least one wrong component to choose against")
    elif t == "system_change":
        for key in ("actionLabel", "beforeStatus", "afterStatus", "result"):
            if not isinstance(e.get(key), str) or not e[key].strip():
                err(unit_name, lesson_id, f"system_change needs non-empty `{key}`")
        if not isinstance(e.get("viz"), dict) or not isinstance(e.get("afterViz"), dict):
            err(unit_name, lesson_id, "system_change needs both `viz` and `afterViz`")
            return
        before_ids = check_viz(unit_name, lesson_id, e["viz"], "system_change before")
        after_ids = check_viz(unit_name, lesson_id, e["afterViz"], "system_change after")
        if set(before_ids) == set(after_ids) and e["viz"] == e["afterViz"]:
            err(unit_name, lesson_id, "system_change before and after diagrams are identical")
        choices = e.get("choices")
        if choices is not None:
            if not isinstance(choices, list) or len(choices) < 2 or any(not isinstance(c, str) or not c.strip() for c in choices):
                err(unit_name, lesson_id, "decision-mode system_change needs at least two non-empty choices")
            answer = e.get("answer")
            if not isinstance(answer, int) or not (0 <= answer < len(choices)):
                err(unit_name, lesson_id, "decision-mode system_change needs an in-range integer `answer`")
            feedback = e.get("choiceFeedback")
            if not isinstance(feedback, list) or len(feedback) != len(choices) or any(not isinstance(x, str) or not x.strip() for x in feedback):
                err(unit_name, lesson_id, "decision-mode system_change needs one non-empty `choiceFeedback` per choice")
        elif "answer" in e or "choiceFeedback" in e:
            err(unit_name, lesson_id, "system_change answer/choiceFeedback require `choices`")
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
        model = sim.get("model") or {"kind": "flow"}
        kind = model.get("kind", "flow")
        if kind not in {"flow", "queue", "retry", "pool"}:
            err(unit_name, lesson_id, f"unknown simulation model {kind!r}")
            return
        required_model = {"queue": {"duration", "servicePerUnit"},
                          "retry": {"retryFraction"},
                          "pool": {"servicePerUnit"}}.get(kind, set())
        missing_model = required_model - set(model)
        if missing_model:
            err(unit_name, lesson_id,
                f"simulation model {kind!r} missing {sorted(missing_model)}")
            return
        for nid in (sim.get("capacity") or {}):
            if nid not in ids:
                err(unit_name, lesson_id, f"sim capacity names unknown node {nid!r}")
        rng = check_answer_range(unit_name, lesson_id, e, ab["min"], ab["max"])
        # `capacity` for the watched node is REQUIRED, not optional. It used to be
        # read with `.get()` and the whole physics check sat behind
        # `if cap is not None` — so deleting `capacity`, or supplying it for some
        # other node, silently skipped the only gate that ties the answer key to
        # the simulation, and the validator said PASS.
        cap = sim_state(sim, ab["start"])[1].get(sim["watch"])
        if cap is None:
            err(unit_name, lesson_id,
                f"simulate needs `capacity` for the watched node {sim['watch']!r} — "
                f"without it there is nothing to check the answerRange against")
            return
        if rng is None:
            return
        # Grade the answer key against the model the learner actually manipulates.
        ok = [p for p in range(int(ab["min"]), int(ab["max"]) + 1)
              if sim_state(sim, p)[0][sim["watch"]] <= sim_state(sim, p)[1][sim["watch"]]]
        if not ok:
            err(unit_name, lesson_id,
                f"simulate is unwinnable: no setting gets {sim['watch']!r} "
                f"under its capacity of {cap}")
            return
        # BOTH directions. The old check only asked whether the range CONTAINED
        # the threshold, never whether every value IN it actually passes — so
        # answerRange [50,92] on a threshold of 90 validated clean, and a learner
        # who set the slider to 50 watched the database glow red at 5x capacity
        # and was told "✓ Nice!". CLAUDE.md claims this check "rejects an
        # answerRange that disagrees with the physics the learner sees"; it only
        # half did.
        losing = [p for p in range(rng[0], rng[1] + 1) if p not in set(ok)]
        if losing:
            worst = sim_state(sim, losing[0])[0][sim["watch"]]
            err(unit_name, lesson_id,
                f"answerRange {rng} accepts {len(losing)} setting(s) that MELT "
                f"{sim['watch']!r} — e.g. {losing[0]}{ab.get('unit','%')} sends {worst:,.0f} "
                f"at a capacity of {cap:,}. The learner would watch it fail and be told they're right.")
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
                return
        rng = check_answer_range(unit_name, lesson_id, e)
        if rng is None:
            return
        # The slider rests at 50. A range straddling it means the learner is
        # correct having never touched the control — three shipped exercises did
        # exactly that ([45,85], [30,70], [40,70]): read nothing, press Check,
        # "✓ Nice!", +10 XP. The renderer now refuses to enable Check until the
        # slider moves, which closes the blind-Check path — but an exercise whose
        # answer sits on the default still can't tell a judgement from a shrug,
        # so it's a warning the author has to look at rather than a hard fail on
        # content that is otherwise honest.
        if rng[0] <= SLIDER_START <= rng[1]:
            warn(unit_name, lesson_id,
                 f"answerRange {rng} contains the slider's resting value "
                 f"({SLIDER_START}) — a learner who never moves it is 'correct'. "
                 f"Move the range off-centre, or accept that this exercise "
                 f"measures nothing.")


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

CONCEPT_RHETORIC = (
    r"\bnot\b.{0,180}\bbut\b|\brather than\b|\bthe opposite\b|"
    r"\bsounds? like\b|\bseems? like\b|\bwork out\b|\bsit with\b|"
    r"\bnotice (?:that|what|how)\b|\bthere(?:'s| is) an obvious\b|"
    r"\bask (?:yourself |)what\b|\bhold that against\b"
)


def advisory(unit_name, lesson_id, e):
    texts = [e.get("why") or "", e.get("goDeeper") or ""]
    if e["type"] == "concept":
        concept_text = " ".join(e.get(k, "") for k in ("title", "body", "note"))
        match = re.search(CONCEPT_RHETORIC, concept_text, re.I | re.S)
        if match:
            warn(unit_name, lesson_id,
                 f"concept uses rhetorical contrast/direction instead of a direct mechanism: "
                 f"{match.group(0)[:100]}")
        texts.extend([e.get("title") or "", e.get("body") or "", e.get("note") or ""])
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

    total_lessons = total_ex = total_simulations = 0
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

        # A checkpoint mixes units already taught, so it tests by design.
        is_checkpoint = "checkpoint" in (d.get("unitId") or "")

        expansion = [e for lesson in d.get("lessons", [])
                     for e in lesson.get("exercises", [])
                     if e.get("diagramExpansion") is True]
        all_exercises = [e for lesson in d.get("lessons", [])
                         for e in lesson.get("exercises", [])]
        transfer = [e for e in all_exercises if e.get("transfer") is True]
        if not transfer:
            errors.append(
                f"{name} :: no transfer exercise — every unit needs at least one "
                "graded unfamiliar application")
        for drill in transfer:
            if drill.get("type") == "concept" or not drill.get("prompt"):
                errors.append(
                    f"{name} :: {drill.get('id')} :: transfer must be a graded "
                    "exercise with an explicit scenario prompt")
        if len(expansion) < 3:
            errors.append(
                f"{name} :: only {len(expansion)} diagram-expansion exercises — "
                "every unit requires at least 3 new interactive diagrams")
        for drill in expansion:
            if drill.get("type") != "build_diagram" or not drill.get("viz"):
                errors.append(
                    f"{name} :: {drill.get('id')} :: diagramExpansion must be an "
                    "interactive build_diagram with a viz")
            # Reconstruction is useful retrieval practice, but the expansion
            # pass exists to add learning—not clone a system_change and count
            # it again. A new drill must pose its own task and explain what the
            # learner inferred from this particular construction.
            peers = [e for e in all_exercises if e.get("id") != drill.get("id")]
            prompt = (drill.get("prompt") or "").strip()
            unwrapped = prompt.removeprefix("Rebuild the repaired topology for: ").strip()
            if any((e.get("prompt") or "").strip() in {prompt, unwrapped}
                   for e in peers if e.get("prompt")):
                errors.append(
                    f"{name} :: {drill.get('id')} :: diagramExpansion repeats an "
                    "existing prompt instead of adding a new architecture task")
            why = (drill.get("why") or "").strip()
            if why and any((e.get("why") or "").strip() == why for e in peers):
                errors.append(
                    f"{name} :: {drill.get('id')} :: diagramExpansion repeats an "
                    "existing `why`; explain the new inference")

        # A design studio must finish by making the learner inspect and revise a
        # complete system. Component recognition alone is not a capstone. Keep
        # this structural and mechanically testable; prose quality still needs
        # review, but a studio cannot silently shrink back to three thin lessons.
        is_design_studio = (d.get("unitId") or "").startswith("design-")
        if is_design_studio:
            lessons = d.get("lessons", [])
            if len(lessons) < 4:
                errors.append(
                    f"{name} :: design studio has {len(lessons)} lessons — minimum 4, "
                    "including a complete-system review")
            if lessons:
                final = lessons[-1]
                title = (final.get("title") or "").lower()
                types = {e.get("type") for e in final.get("exercises", [])}
                required = {"concept", "system_change", "build_diagram", "multi_select"}
                if "review" not in title:
                    errors.append(
                        f"{name} :: final lesson must be an explicit design review, got "
                        f"{final.get('title')!r}")
                missing_review = required - types
                if missing_review:
                    errors.append(
                        f"{name} :: {final.get('id')} :: design review missing exercise "
                        f"type(s) {sorted(missing_review)}")

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

            # THE RAMP PRINCIPLE (CONTENT_MASTER.md 6.1, owner directive).
            # Every teaching lesson opens by teaching. A building has a ramp even
            # though most people take the stairs; low usage is not a reason to
            # fail the people who need it. Advanced learners get a one-tap skip
            # in the app — that's the stairs, and it's why this can be mandatory
            # without taxing anyone. Checkpoints are exempt: a checkpoint is a
            # test by design, mixing units the learner was already taught.
            if exs and not is_checkpoint and exs[0].get("type") != "concept":
                errors.append(
                    f"{name} :: {lid} :: opens with `{exs[0].get('type')}` — every "
                    f"lesson must open with a `concept` card (CONTENT_MASTER 6.1). "
                    f"Testing before teaching is the thing this rule exists to stop.")

            if n_concept > CONCEPT_MAX_PER_LESSON:
                errors.append(f"{name} :: {lid} :: {n_concept} concept cards — max "
                              f"{CONCEPT_MAX_PER_LESSON} per lesson. Teaching beats are "
                              f"punctuation; past this the learner is reading, not playing.")
            if n_concept and all(e.get("type") == "concept" for e in exs):
                errors.append(f"{name} :: {lid} :: every card is a concept — a lesson "
                              f"that never asks anything is a slide deck")

            for e in exs:
                total_ex += 1
                if e.get("type") == "simulate":
                    total_simulations += 1
                check_exercise(n, name, lid, e)
                if not quiet:
                    advisory(name, lid, e)

                # source <-> embed drift.
                # The embed stores each string as a JSON string literal, so compare against
                # the escaped form — a raw compare false-positives on any content containing
                # a double quote (e.g. unit 3's '{"error": "user not found"}').
                #
                # This list used to stop at prompt/why/title/body/note/choices/
                # steps/palette/viz. Everything below it was invisible to the one
                # gate that exists to catch drift — including `pairs`, which IS
                # the match_pairs ANSWER KEY. An author could edit a pairing, run
                # the documented per-change gate, get PASS, and ship a prototype
                # still serving the old pairs and the old key.
                for frag in embed_fragments(e):
                    if frag and embed_form(frag) not in html:
                        err(name, lid, f"NOT IN PROTOTYPE EMBED: {frag[:70]!r}")

    if total_simulations < 30:
        errors.append(
            f"only {total_simulations} causal simulations course-wide — course floor is 30")

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
