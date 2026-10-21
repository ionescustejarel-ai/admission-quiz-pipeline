"""Build the quiz: questions_clean.json + enriched/*.json -> one offline HTML file.

    python pipeline/build_quiz.py --data sample --out build/quiz.html

- questions_clean.json holds what was read from the booklet: chapter, number,
  stem, options and the official answer key.
- enriched/enriched_capNN.json holds what was added per question: syllabus
  sub-section, excluded flag, a verbatim quote from the source manual
  (`evidence`) with its page, an explanation (`why`) and, for false
  statements, the corrected form (`fix`).

The two are joined by chapter and question number and injected into the
template as a single `const DATA = {...};` line. A final data snapshot is
written next to the HTML so it can be audited with audit_fix.py.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_TEMPLATE = os.path.join(HERE, "..", "app", "quiz_template.html")


def load_enriched(data_dir, cap, warn):
    path = os.path.join(data_dir, "enriched", f"enriched_cap{cap:02d}.json")
    if not os.path.exists(path):
        warn.append(f"cap{cap}: enriched missing -> no exclusions/evidence")
        return {}
    try:
        return {str(e["num"]): e for e in json.load(open(path, encoding="utf-8"))}
    except (ValueError, KeyError) as ex:
        warn.append(f"cap{cap}: bad enriched json ({ex})")
        return {}


def merge(data_dir):
    clean = json.load(open(os.path.join(data_dir, "questions_clean.json"), encoding="utf-8"))
    out, warn = {"chapters": []}, []
    for c in clean["chapters"]:
        cap = int(c["num"])
        emap = load_enriched(data_dir, cap, warn)
        qs = []
        for q in c["questions"]:
            e = emap.get(str(q["num"]), {})
            qs.append({
                "num": q["num"], "stem": q["stem"], "options": q["options"], "answer": q["answer"],
                "source": e.get("source", "oficial"), "confidence": "high",
                "via": e.get("via", "cheie oficială"),
                "excluded": bool(e.get("excluded", False)),
                "subsection": e.get("subsection", "") or "",
                "evidence": e.get("evidence", "") or "",
                "page": e.get("page"),
                "note": "", "why": e.get("why", "") or "", "truth": "",
                "fix": e.get("fix", "") or "",
            })
        out["chapters"].append({"num": cap, "title": c["title"], "excl": c.get("excl", ""), "questions": qs})
    return out, warn


def render(data, template, title, storage_key):
    src = open(template, encoding="utf-8").read()
    lines = src.split("\n")
    idx = [i for i, ln in enumerate(lines) if ln.lstrip().startswith("const DATA = {")]
    assert len(idx) == 1, f"expected one DATA line in template, found {len(idx)}"
    lines[idx[0]] = "const DATA = " + json.dumps(data, ensure_ascii=False) + ";"
    src = "\n".join(lines)
    return src.replace("{{TITLE}}", title).replace("{{STORAGE_KEY}}", storage_key)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data", required=True, help="folder with questions_clean.json and enriched/")
    ap.add_argument("--out", required=True, help="output HTML path")
    ap.add_argument("--template", default=DEFAULT_TEMPLATE)
    ap.add_argument("--title", default="Grile — test interactiv")
    ap.add_argument("--storage-key", default="quiz_progress")
    args = ap.parse_args(argv)

    data, warn = merge(args.data)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    snap = os.path.splitext(args.out)[0] + "_data.json"
    json.dump(data, open(snap, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    html = render(data, args.template, args.title, args.storage_key)
    open(args.out, "w", encoding="utf-8", newline="").write(html)

    sys.stdout.reconfigure(encoding="utf-8")
    tot = sum(len(c["questions"]) for c in data["chapters"])
    inc = sum(1 for c in data["chapters"] for q in c["questions"] if not q["excluded"])
    ev = sum(1 for c in data["chapters"] for q in c["questions"] if q["evidence"])
    print(f"wrote {args.out} and {snap}")
    print(f"questions={tot} included={inc} excluded={tot - inc} with_evidence={ev}")
    for w in warn:
        print("  !", w)
    return 0


if __name__ == "__main__":
    sys.exit(main())
