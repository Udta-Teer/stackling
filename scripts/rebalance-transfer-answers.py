#!/usr/bin/env python3
"""Emit a patch distributing transfer answer positions across A-D."""
import difflib, json
from pathlib import Path

print("*** Begin Patch")
for index, path in enumerate(sorted(Path("content").glob("*.json"))):
    before = path.read_text()
    unit = json.loads(before)
    shift = index % 4
    changed = False
    for lesson in unit["lessons"]:
        for ex in lesson["exercises"]:
            if ex.get("transfer") is not True or ex.get("type") != "multiple_choice":
                continue
            choices = ex["choices"]
            answer = ex["answer"]
            if shift:
                ex["choices"] = choices[-shift:] + choices[:-shift]
                ex["answer"] = (answer + shift) % len(choices)
            changed = True
    if not changed:
        continue
    after = json.dumps(unit, ensure_ascii=False, indent=2) + "\n"
    diff = list(difflib.unified_diff(before.splitlines(), after.splitlines(), lineterm=""))[2:]
    diff = ["@@" if line.startswith("@@ ") else line for line in diff]
    print(f"*** Update File: {path}")
    print("\n".join(diff))
print("*** End Patch")
