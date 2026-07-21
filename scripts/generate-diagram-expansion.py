#!/usr/bin/env python3
"""Emit an apply_patch patch adding three topology-reconstruction drills.

The drills are derived from already reviewed diagrams in one unit. This keeps
the new interaction factually aligned with the course instead of generating
129 unrelated architectures merely to satisfy a count. The script never writes
files; its stdout is passed to the repository's apply_patch tool.
"""
import copy
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def complete_viz(ex, key):
    viz = copy.deepcopy(ex[key])
    answer = ex.get("answer") if isinstance(ex.get("answer"), dict) else {}
    for node in viz.get("nodes", []):
        if node.get("hole"):
            label = answer.get(node.get("id"))
            if not label:
                return None
            node["label"] = label
            node.pop("hole", None)
    return viz


def candidates(unit):
    rows = []
    for lesson in unit.get("lessons", []):
        for pos, ex in enumerate(lesson.get("exercises", [])):
            sources = []
            if ex.get("afterViz"):
                sources.append((0, "afterViz", "repaired"))
                if ex.get("viz"):
                    # Failure topologies are useful reconstruction drills too:
                    # the learner must be able to recognize the system that
                    # produced the measured failure before repairing it.
                    sources.append((3, "viz", "failing"))
            if ex.get("type") == "concept" and ex.get("viz"):
                sources.append((1, "viz", "core"))
            if ex.get("type") == "build_diagram" and ex.get("viz"):
                sources.append((2, "viz", "complete"))
            if ex.get("viz") and not sources:
                sources.append((3, "viz", "observed"))
            for priority, key, flavor in sources:
                viz = complete_viz(ex, key)
                if not viz or len(viz.get("nodes", [])) < 2:
                    continue
                rows.append({"priority": priority, "lesson": lesson,
                             "pos": pos, "ex": ex, "viz": viz,
                             "flavor": flavor})
    rows.sort(key=lambda r: (r["priority"], r["pos"]))
    # First spread drills across lessons; only reuse a lesson when necessary.
    chosen, used_lessons = [], set()
    for row in rows:
        if row["lesson"]["id"] not in used_lessons:
            chosen.append(row); used_lessons.add(row["lesson"]["id"])
            if len(chosen) == 3:
                return chosen
    for row in rows:
        if row not in chosen:
            chosen.append(row)
            if len(chosen) == 3:
                return chosen
    return chosen


def make_drill(unit, row, number):
    viz = copy.deepcopy(row["viz"])
    nodes = viz["nodes"]
    min_col = min(n.get("col", 0) for n in nodes)
    eligible = [n for n in nodes if n.get("label") and
                (n.get("col", 0) != min_col or len(nodes) <= 2)]
    if not eligible:
        eligible = [n for n in nodes if n.get("label")]
    # Two or three missing components produces reconstruction rather than an
    # obvious one-box vocabulary check. Tiny two-node diagrams necessarily use one.
    holes = eligible[:min(3, max(1, len(eligible)))]
    answers = {n["id"]: n["label"] for n in holes}
    answer_labels = list(answers.values())

    # Pull plausible distractors from the unit's own vocabulary.
    vocabulary = []
    for lesson in unit["lessons"]:
        for ex in lesson["exercises"]:
            for key in ("viz", "afterViz"):
                for node in (ex.get(key) or {}).get("nodes", []):
                    label = node.get("label")
                    if label and label not in vocabulary:
                        vocabulary.append(label)
    diagram_labels = {n.get("label") for n in nodes}
    distractors = [x for x in vocabulary if x not in answer_labels and
                   x not in diagram_labels][:2]
    for fallback in ("Unrelated analytics worker", "Client-only memory"):
        if len(distractors) >= 2: break
        if fallback not in answer_labels: distractors.append(fallback)

    for node in nodes:
        if node["id"] in answers:
            node.pop("label", None)
            node.pop("kind", None)
            node["hole"] = True

    source = row["ex"].get("title") or row["ex"].get("prompt") or row["lesson"]["title"]
    why = row["ex"].get("why") or row["ex"].get("body") or ""
    if row["ex"].get("note"):
        why = (why + " " + row["ex"]["note"]).strip()
    return {
        "id": f"{unit['unitId']}-diagram-drill-{number}",
        "type": "build_diagram",
        "diagramExpansion": True,
        "prompt": f"Rebuild the {row['flavor']} topology for: {source}",
        "viz": viz,
        "palette": answer_labels + distractors,
        "answer": answers,
        "why": why,
    }


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: generate-diagram-expansion.py content/NN-file.json")
    rel = sys.argv[1]
    path = os.path.join(ROOT, rel)
    unit = json.load(open(path, encoding="utf-8"))
    existing = sum(e.get("diagramExpansion") is True
                   for l in unit.get("lessons", []) for e in l.get("exercises", []))
    if existing >= 3:
        return
    rows = candidates(unit)
    if len(rows) < 3:
        raise SystemExit(f"{rel}: only {len(rows)} usable reviewed topologies")
    # Insert immediately after each source so teaching and reconstruction stay
    # adjacent. Reverse source positions avoid index drift within one lesson.
    additions = []
    for i, row in enumerate(rows[:3], 1):
        additions.append((row["lesson"], row["pos"], make_drill(unit, row, i)))
    for lesson in unit["lessons"]:
        local = sorted((x for x in additions if x[0] is lesson),
                       key=lambda x: x[1], reverse=True)
        for _, pos, drill in local:
            lesson["exercises"].insert(pos + 1, drill)

    rendered = json.dumps(unit, ensure_ascii=False, indent=2) + "\n"
    print("*** Begin Patch")
    print(f"*** Delete File: {os.path.join(ROOT, rel)}")
    print(f"*** Add File: {os.path.join(ROOT, rel)}")
    for line in rendered.splitlines():
        print("+" + line)
    print("*** End Patch")


if __name__ == "__main__":
    main()
