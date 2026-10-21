"""Audit: does any `fix` block contradict the official answer key?

The `fix` field rewrites a false statement into its correct form. It is
written per question, so it can drift from the key. Two contradiction
shapes were found in practice:
  1. the line for the keyed letter argues that letter is FALSE  ("A — ... NU sunt ...")
  2. the fix crowns a different letter as correct               ("(E corect: ...)")

Usage: python pipeline/audit_fix.py build/data_final.json
Exit code 1 if any contradiction is found, so it can gate a build.
"""
import json
import re
import sys

NEG = re.compile(r"\bNU\b|\bnu (?:e|este|sunt)\b", re.I)
# "(E corect: ...)" drops the copula, so the verb has to be optional
CROWN = re.compile(r"\b([A-E])\s+(?:e\s+|este\s+)?corect", re.I)


def audit(data):
    """Return a list of (chapter, question, key, reasons, stem) for contradictions."""
    hits = []
    for ch in data["chapters"]:
        for q in ch["questions"]:
            fix, ans = q.get("fix") or "", q["answer"]
            if not fix:
                continue
            reasons = []
            # shape 1: the line that starts with the keyed letter argues it is false
            for line in fix.split("\n"):
                m = re.match(r"\s*([A-E])\s*[—\-–]", line)
                if m and m.group(1) == ans and NEG.search(line):
                    reasons.append(f"line for keyed {ans} argues it FALSE: {line.strip()!r}")
            # shape 2: a different letter is crowned correct
            for m in CROWN.finditer(fix):
                if m.group(1).upper() != ans:
                    reasons.append(f"crowns {m.group(1).upper()} correct but key={ans}")
            if reasons:
                hits.append((ch["num"], q["num"], ans, reasons, q["stem"][:70]))
    return hits


def main(path):
    sys.stdout.reconfigure(encoding="utf-8")
    data = json.load(open(path, encoding="utf-8"))
    hits = audit(data)
    n_fix = sum(1 for c in data["chapters"] for q in c["questions"] if q.get("fix"))
    print(f"questions with fix: {n_fix}")
    print(f"contradictions: {len(hits)}\n")
    for cap, num, ans, reasons, stem in hits:
        print(f"cap{cap} q{num} (key={ans}) — {stem}")
        for r in reasons:
            print("   !", r)
    return 1 if hits else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1]))
