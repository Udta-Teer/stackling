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

# goDeeper was retired from this unit onward. See CONTENT_MASTER.md 3.1.
# Units below this keep theirs; the owner is revisiting them separately.
GODEEPER_RETIRED_FROM = 12

ALLOWED_FIELDS = {
    "type", "prompt", "choices", "answer", "why", "hint",
    "pairs", "steps", "slots", "palette",
    "tolerance", "unit", "leftLabel", "rightLabel", "answerRange",
    "goDeeper",  # legacy only; separately rejected for units >= GODEEPER_RETIRED_FROM
}

KNOWN_TYPES = {
    "multiple_choice", "fill_blank", "multi_select", "match_pairs",
    "order_steps", "build_diagram", "estimate", "tradeoff_slider",
    "spot_bottleneck",
}

errors = []
warnings = []


def err(unit, lesson, msg):
    errors.append(f"{unit} :: {lesson} :: {msg}")


def warn(unit, lesson, msg):
    warnings.append(f"{unit} :: {lesson} :: {msg}")


def unit_number(path):
    base = os.path.basename(path)
    m = re.match(r"(\d+)", base)
    return int(m.group(1)) if m else None


def check_exercise(unit_no, unit_name, lesson_id, e):
    t = e.get("type")
    if t not in KNOWN_TYPES:
        err(unit_name, lesson_id, f"unknown exercise type: {t!r}")
        return

    stray = set(e) - ALLOWED_FIELDS
    if stray:
        err(unit_name, lesson_id, f"stray field(s): {sorted(stray)}")

    if not e.get("why"):
        err(unit_name, lesson_id, "missing or empty `why`")

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
    elif t == "build_diagram":
        if "?" not in (e.get("slots") or []):
            err(unit_name, lesson_id, "build_diagram needs a '?' slot")
        if e.get("answer") not in (e.get("palette") or []):
            err(unit_name, lesson_id, "build_diagram answer must be in palette")
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

        for lesson in d.get("lessons", []):
            lid = lesson.get("id", "<no id>")
            total_lessons += 1
            for e in lesson.get("exercises", []):
                total_ex += 1
                check_exercise(n, name, lid, e)
                if not quiet:
                    advisory(name, lid, e)

                # source <-> embed drift.
                # The embed stores each string as a JSON string literal, so compare against
                # the escaped form — a raw compare false-positives on any content containing
                # a double quote (e.g. unit 3's '{"error": "user not found"}').
                fragments = [e.get("prompt", ""), e.get("why", "")]
                fragments += list(e.get("choices", []) or [])
                fragments += list(e.get("steps", []) or [])
                for frag in fragments:
                    if frag and json.dumps(frag, ensure_ascii=False)[1:-1] not in html:
                        err(name, lid, f"NOT IN PROTOTYPE EMBED: {frag[:70]!r}")

    print(f"content: {len(files)} units, {total_lessons} lessons, {total_ex} exercises")
    print(f"goDeeper retired from unit {GODEEPER_RETIRED_FROM} onward")

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
