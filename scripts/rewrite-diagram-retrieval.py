#!/usr/bin/env python3
"""Emit an apply_patch patch that turns cloned expansion drills into explicit retrieval builds.

This script never writes content. The caller reviews and applies its patch.
"""
import difflib
import json
import sys
from pathlib import Path


def serial(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def resolved_label(node, answer):
    return answer.get(node.get("id"), node.get("label", node.get("id", "component")))


files = [Path(arg) for arg in sys.argv[1:]]
print("*** Begin Patch")
for path in files:
    before = path.read_text()
    unit = json.loads(before)
    exercises = [e for lesson in unit["lessons"] for e in lesson["exercises"]]
    changed = False
    for drill in [e for e in exercises if e.get("diagramExpansion") is True]:
        peers = [e for e in exercises if e.get("id") != drill.get("id")]
        prompt = drill.get("prompt", "").strip()
        bare = prompt.removeprefix("Rebuild the repaired topology for: ").strip()
        prompt_copy = any((e.get("prompt") or "").strip() in {prompt, bare}
                          for e in peers if e.get("prompt"))
        why_copy = any((e.get("why") or "").strip() == (drill.get("why") or "").strip()
                       for e in peers)
        if not prompt_copy and not why_copy:
            continue

        answer = drill.get("answer", {})
        components = list(dict.fromkeys(answer.values()))
        node_labels = {n["id"]: resolved_label(n, answer)
                       for n in drill.get("viz", {}).get("nodes", [])}
        edges = []
        for edge in drill.get("viz", {}).get("edges", []):
            left = node_labels.get(edge.get("from"), edge.get("from", "?"))
            right = node_labels.get(edge.get("to"), edge.get("to", "?"))
            edges.append(f"{left} → {right}")
        path_text = "; ".join(edges)

        if prompt_copy:
            scenario = bare.rstrip(".")
            drill["prompt"] = (
                f"Reconstruct this architecture from memory: {scenario}. "
                f"Place {', '.join(components)} and make every arrow represent a real call or data flow."
            )
        if why_copy:
            original = drill.get("why", "").strip()
            drill["why"] = (
                f"The completed diagram contains these directed flows: {path_text}. "
                f"That topology is the evidence for the answer: {original}"
            )
        changed = True

    if not changed:
        continue
    after = serial(unit)
    diff = list(difflib.unified_diff(before.splitlines(), after.splitlines(), lineterm=""))[2:]
    # Codex's patch applier accepts standard hunk bodies but uses a bare `@@`
    # delimiter instead of line-number ranges.
    diff = ["@@" if line.startswith("@@ ") else line for line in diff]
    print(f"*** Update File: {path}")
    print("\n".join(diff))
print("*** End Patch")
