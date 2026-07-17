#!/usr/bin/env python3
"""
Find concept cards that hand over their own lesson's graded answers.

A card MUST make the lesson's FIRST exercise answerable — that's its whole job
(CONTENT_MASTER.md 6.1), so overlap there is by design and is not reported by
default. What this catches is a card that goes further and pre-answers exercises
2..N, turning inference into recall: the learner reads the answer, then gets
asked the question.

The healthy shape is: teach the METHOD on one instance, test on a DIFFERENT one.
`rl-3-0` -> `rl-3-1` and `cache-3-0` -> `cache-3-sim` both do this.

Detection is word-shingle containment: what fraction of the graded answer's
5-word shingles already appear in the card? Verbatim lifts score ~1.0.

⚠ WHAT THIS CANNOT DO — read before trusting a clean run.
This catches COPY-PASTE, not spoilers. The worst real spoilers are semantic: the
card conveys the idea in different words, so no lexical measure sees them.
Calibrated against cases a human reviewer confirmed:

    scale-4-0 -> scale-4-5   "a complete pre-answer"      scored   0%
    cdn-4-0   -> cdn-4-4     lists all 3 correct options  scored   0%
    rl-3-0    -> rl-3-1      HEALTHY (the model to copy)  scored  25%

The healthy card scores HIGHER than the two worst offenders. A clean run here
means "nobody copy-pasted", and nothing more. Judging whether a learner could
answer by recall instead of reasoning needs a reader, not a threshold — so this
is a cheap regression gate, not the review.

Usage:
    python3 scripts/check-spoilers.py            # report
    python3 scripts/check-spoilers.py --strict   # exit 1 if any exercise 2..N is spoiled
    python3 scripts/check-spoilers.py --first    # also report exercise 1 overlap (advisory)
"""

import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
N = 5                 # shingle width for long answers
MIN_WORDS = 3         # below this, an answer is a vocabulary word, not a spoiler:
                      # a card teaching what a cache IS must say "cache", and a
                      # fill_blank answered "cache" is a deliberate check, not a leak.
MIN_NUMBER = 100      # small integers appear everywhere; only distinctive figures count
THRESHOLD = 0.60      # fraction of an answer's shingles already on the card


def norm(s):
    """Strip markdown and punctuation so a lift is caught regardless of styling."""
    s = str(s or "").lower()
    s = s.replace("`", " ").replace("*", " ")
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def shingles(s, n=N):
    w = norm(s).split()
    n = min(n, len(w))
    if n < MIN_WORDS:
        return set()
    return {" ".join(w[i:i + n]) for i in range(len(w) - n + 1)}


def card_text(card):
    parts = [card.get("title", ""), card.get("body", ""), card.get("note", "")]
    for node in (card.get("viz") or {}).get("nodes", []) or []:
        parts += [node.get("label", ""), node.get("sub", "")]
    return " ".join(parts)


def answer_texts(e):
    """Everything the learner is supposed to PRODUCE, as text."""
    t = e.get("type")
    ch = e.get("choices") or []
    if t in ("multiple_choice", "fill_blank"):
        i = e.get("answer")
        return [ch[i]] if isinstance(i, int) and i < len(ch) else []
    if t == "multi_select":
        return [ch[i] for i in (e.get("answer") or []) if i < len(ch)]
    if t == "match_pairs":
        return [f"{p.get('left','')} {p.get('right','')}" for p in e.get("pairs") or []]
    if t == "order_steps":
        return [" ".join(e.get("steps") or [])]      # the ORDER is the answer
    if t == "build_diagram":
        a = e.get("answer")
        return list(a.values()) if isinstance(a, dict) else []
    if t == "spot_bottleneck":
        nodes = e.get("viz", {}).get("nodes") if e.get("viz") else e.get("nodes")
        i = e.get("answer")
        if isinstance(nodes, list) and isinstance(i, int) and i < len(nodes):
            n = nodes[i]
            return [n.get("label", "") if isinstance(n, dict) else str(n)]
    return []


def numeric_answer(e):
    if e.get("type") == "estimate":
        return e.get("answer")
    return None


def score(card_txt, ans):
    """Fraction of the answer's shingles already present in the card.

    Answers under MIN_WORDS score 0: they're single vocabulary terms the card is
    obliged to use. Scoring them flagged every `fill_blank` in the course at
    100% and buried the real lifts.
    """
    a = shingles(ans)
    if not a:
        return 0.0
    return len(a & shingles(card_txt)) / len(a)


def main():
    strict = "--strict" in sys.argv
    show_first = "--first" in sys.argv
    hits, first_hits = [], []

    files = sorted(glob.glob(os.path.join(ROOT, "content", "*.json")),
                   key=lambda p: int(re.match(r"(\d+)", os.path.basename(p)).group(1)))
    for f in files:
        d = json.load(open(f, encoding="utf-8"))
        name = os.path.basename(f)
        for lesson in d.get("lessons", []):
            exs = lesson.get("exercises", [])
            if not exs or exs[0].get("type") != "concept":
                continue
            card = exs[0]
            ctext = card_text(card)
            for pos, e in enumerate(exs[1:], start=1):
                if e.get("type") == "concept":
                    continue
                worst, what = 0.0, None
                for ans in answer_texts(e):
                    s = score(ctext, ans)
                    if s > worst:
                        worst, what = s, ans
                # A number only counts as given away if it appears WITH its unit.
                # Bare "\b10\b" matched "10 million rows" straight out of the
                # prompt, which is context the card is supposed to share.
                num = numeric_answer(e)
                if num is not None and num >= MIN_NUMBER:
                    unit = norm(e.get("unit", "")).split()
                    u = unit[0][:4] if unit else ""
                    pat = r"\b(" + re.escape(f"{num:,}") + r"|" + re.escape(str(num)) + r")\b[^.]{0,18}" + re.escape(u)
                    if re.search(pat, norm(ctext).replace(",", "") ) or re.search(pat, norm(ctext)):
                        worst, what = 1.0, f"the number {num} {e.get('unit','')} it asks the learner to compute"
                if worst >= THRESHOLD:
                    rec = (name, lesson.get("id"), card["id"], e["id"], pos, worst, what)
                    (first_hits if pos == 1 else hits).append(rec)

    def show(rows, header):
        print(f"\n{header}")
        if not rows:
            print("  none")
            return
        for name, lid, cid, eid, pos, s, what in rows:
            print(f"  {s*100:3.0f}%  {cid:12} -> {eid:12} (exercise {pos})  {name[:22]}")
            print(f"        gives away: {str(what)[:88]}")

    show(hits, f"SPOILED — card pre-answers exercise 2..N ({len(hits)}):")
    if show_first:
        show(first_hits, f"exercise 1 overlap — by design, advisory only ({len(first_hits)}):")

    print(f"\n{len(hits)} spoiled exercise(s) beyond the first"
          f"{f', {len(first_hits)} first-exercise overlaps' if show_first else ''}")
    if strict and hits:
        print("FAIL: a card is answering questions the learner is about to be asked.",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
