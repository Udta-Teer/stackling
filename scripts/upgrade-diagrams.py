#!/usr/bin/env python3
"""One-time migration for the 2026 diagram-quality audit.

Makes edge meaning explicit, repairs known misleading diagrams, replaces the
generated reconstruction boilerplate, and promotes one expansion per unit into
an interaction where the learner must connect the placed components.
"""
import glob
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def edge_kind(edge, nodes):
    if edge.get("kind"):
        return edge["kind"]
    if edge.get("dash"):
        return "optional"
    a, b = nodes.get(edge.get("from"), {}), nodes.get(edge.get("to"), {})
    kinds = {a.get("kind"), b.get("kind")}
    if "queue" in kinds:
        return "event"
    if "dns" in kinds:
        return "control"
    if kinds & {"db", "cache", "storage"}:
        return "data"
    return "request"


def enrich(viz):
    if not isinstance(viz, dict):
        return
    nodes = {n.get("id"): n for n in viz.get("nodes", [])}
    for edge in viz.get("edges", []):
        edge["kind"] = edge_kind(edge, nodes)


def concise_prompt(ex, lesson_title):
    prompt = ex.get("prompt", "")
    # Generated drills contained a scenario followed by mechanical instructions.
    m = re.match(r"(?:Reconstruct this architecture from memory|Rebuild the (?:core|complete|failing) topology):\s*(.*?)\s+Place\s+(.+?)\s+and make every arrow represent a real call or data flow\.$", prompt)
    if not m:
        prefixes = {
            "Rebuild the core topology for: ": "Show the minimum components and flows that implement this mechanism: ",
            "Rebuild the complete topology for: ": "Build the end-to-end path required by this scenario: ",
            "Rebuild the failing topology for: ": "Draw the failure path first; the disconnected or blocked part is evidence: ",
        }
        for old, new in prefixes.items():
            if prompt.startswith(old):
                ex["prompt"] = new + prompt[len(old):]
                return
        return
    scenario, components = m.groups()
    count = len(ex.get("answer", {}))
    verb = "Assemble" if count >= 3 else "Complete"
    ex["prompt"] = f"{verb} the system for this case: {scenario} Place {components}. Then connect the components in the direction that requests, data, or events move."


def repair_special(ex):
    eid = ex.get("id")
    if eid == "csh-change-1":
        ex["viz"]["edges"] = [{"from": "b", "to": "s", "kind": "request", "count": 4, "label": "4 connections"}]
        ex["afterViz"]["edges"] = [{"from": "b", "to": "s", "kind": "request", "label": "4 streams · 1 connection"}]
    elif eid == "cap-change-1":
        for key in ("viz", "afterViz"):
            v = ex[key]
            v["nodes"] = [n for n in v["nodes"] if n.get("id") != "x"]
            v["nodes"][0]["col"] = 0
            v["nodes"][1]["col"] = 1
            v["edges"] = [{"from": "a", "to": "b", "kind": "broken", "label": "network partition"}]
    elif eid == "cap-theorem-diagram-drill-1":
        ex["prompt"] = "A network partition isolates Replica B. Place the two replicas, connect their replication link, and show that the link is broken while Replica B rejects writes."
        ex["viz"] = {
            "nodes": [
                {"id": "a", "sub": "accepts writes", "col": 0, "hole": True},
                {"id": "b", "sub": "writes unavailable", "col": 1, "hole": True},
            ],
            "edges": [{"from": "a", "to": "b", "kind": "broken", "label": "network partition"}],
        }
        ex["palette"] = ["Replica A", "Replica B", "Load balancer", "Cache"]
        ex["answer"] = {"a": "Replica A", "b": "Replica B"}
        ex["why"] = "A partition is a failed communication link between replicas, not a component that processes traffic. Replica B rejects writes because it cannot prove that it still has authority; allowing both sides to commit could create conflicting balances."
    elif eid == "sec-2-0" and not any(e.get("to") == "p" for e in ex["viz"]["edges"]):
        ex["viz"]["edges"].append({"from": "w", "to": "p", "kind": "blocked", "label": "permission denied"})
    elif eid == "stream-change-2" and not any(e.get("to") == "d" for e in ex["viz"]["edges"]):
        ex["viz"]["edges"].append({"from": "o", "to": "d", "kind": "broken", "label": "crash · output skipped"})
    elif eid == "hiw-change-1":
        ex["viz"]["edges"] = [
            {"from": "c", "to": "r1", "kind": "request"},
            {"from": "r1", "to": "s", "kind": "broken", "label": "router offline"},
        ]
    elif eid in {"cp1-change-1", "checkpoint-foundations-diagram-drill-3"}:
        ex["viz"]["edges"] = [
            {"from": "c", "to": "a", "kind": "request", "label": "all traffic"},
            {"from": "c", "to": "b", "kind": "blocked", "label": "no route"},
        ]
    elif eid == "chat-change-2":
        ex["viz"]["edges"] = [
            {"from": "a", "to": "g2", "kind": "request"},
            {"from": "g2", "to": "g7", "kind": "blocked", "label": "socket owner unknown"},
        ]
    elif eid == "cons-change-1":
        v = ex["viz"]
        # The absence of replication is the failure being taught; draw it as a
        # failed flow instead of leaving followers as unexplained islands.
        if any(n.get("id") == "l" for n in v["nodes"]):
            v["edges"] = [
                {"from": "c", "to": "l", "kind": "request"},
                {"from": "l", "to": "f1", "kind": "broken", "label": "not replicated"},
                {"from": "l", "to": "f2", "kind": "broken", "label": "not replicated"},
            ]
    elif eid == "consensus-diagram-drill-1":
        ex["viz"]["edges"] = [
            {"from": "c", "to": "l", "kind": "request"},
            {"from": "l", "to": "f1", "kind": "replication", "label": "quorum copy"},
            {"from": "l", "to": "f2", "kind": "optional", "label": "may lag"},
        ]


def main():
    totals = {"files": 0, "edges": 0, "rewritten": 0, "connect": 0}
    for path in sorted(glob.glob(os.path.join(ROOT, "content", "*.json"))):
        with open(path, encoding="utf-8") as f:
            unit = json.load(f)
        promoted = any(e.get("connectEdges") for lesson in unit.get("lessons", [])
                       for e in lesson.get("exercises", []))
        for lesson in unit.get("lessons", []):
            for ex in lesson.get("exercises", []):
                repair_special(ex)
                for key in ("viz", "afterViz"):
                    enrich(ex.get(key))
                    totals["edges"] += len((ex.get(key) or {}).get("edges", []))
                before = ex.get("prompt")
                if ex.get("diagramExpansion"):
                    concise_prompt(ex, lesson.get("title", ""))
                    totals["rewritten"] += ex.get("prompt") != before
                    if not promoted and (ex.get("viz") or {}).get("edges"):
                        ex["connectEdges"] = True
                        promoted = True
                        totals["connect"] += 1
        with open(path, "w", encoding="utf-8") as f:
            json.dump(unit, f, ensure_ascii=False, indent=2)
            f.write("\n")
        totals["files"] += 1
    print(totals)


if __name__ == "__main__":
    main()
