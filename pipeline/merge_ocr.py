"""Merge per-page extraction batches into chapter-ordered questions with answers.

    python pipeline/merge_ocr.py --batches ocr_batches --pages 195 --chapters 3,6,8 --out questions_raw.json

Each batch file is a list of page records produced by the extraction step
(one record per photographed page):

    {"idx": 0, "page_num": 7,
     "chapter_header": {"cap": 1, "title": "..."} | null,
     "questions": [{"num": 1, "stem": "...", "options": {"A": "...", ...}}],
     "key_tables": [{"cap": 1, "title": "...", "answers": {"1": "D", ...}}]}

Pages are walked in order and the current chapter is carried forward, because
most pages have no chapter header. Answer-key tables (printed at the end of the
booklet) are joined back to their questions. Illegible text is marked "[?]" by
the extraction step and reported here, together with questions that have no
key, numbering gaps, duplicates and missing pages.
"""
import argparse
import glob
import json
import os
import sys


def load_batches(folder, n_pages):
    recs = {}
    for f in sorted(glob.glob(os.path.join(folder, "batch_*.json"))):
        try:
            arr = json.load(open(f, encoding="utf-8"))
        except ValueError as e:
            print("!! bad json:", os.path.basename(f), e)
            continue
        for r in arr:
            if r.get("idx") is not None:
                recs[r["idx"]] = r
    missing = [i for i in range(n_pages) if i not in recs]
    return recs, missing


def merge(recs, target):
    cur_cap, cur_title = None, None
    questions, answers, key_titles, flags = [], {}, {}, []
    for idx in sorted(recs):
        r = recs[idx]
        hdr = r.get("chapter_header")
        if hdr and hdr.get("cap") is not None:
            cur_cap, cur_title = hdr["cap"], hdr.get("title", cur_title)
        for q in r.get("questions") or []:
            questions.append({"cap": cur_cap, "title": cur_title, "num": q.get("num"),
                              "stem": (q.get("stem") or "").strip(), "options": q.get("options") or {}})
            blob = q.get("stem", "") + " " + " ".join((q.get("options") or {}).values())
            if "[?]" in blob:
                flags.append(("illegible", cur_cap, q.get("num"), idx))
        for kt in r.get("key_tables") or []:
            cap = kt.get("cap")
            if cap is None:
                continue
            key_titles[cap] = kt.get("title", key_titles.get(cap))
            answers.setdefault(cap, {}).update({str(k): v for k, v in (kt.get("answers") or {}).items()})

    by_cap = {}
    for q in questions:
        if q["cap"] not in target:
            continue
        ans = answers.get(q["cap"], {}).get(str(q["num"]))
        by_cap.setdefault(q["cap"], []).append({**q, "answer": ans})
        if ans is None:
            flags.append(("no_answer", q["cap"], q["num"], None))
    return by_cap, answers, key_titles, flags


def report(by_cap, answers, flags, missing):
    print("pages missing:", missing)
    for cap in sorted(by_cap):
        nums = [x["num"] for x in by_cap[cap] if isinstance(x["num"], int)]
        dup = sorted(n for n in set(nums) if nums.count(n) > 1)
        gaps = sorted(set(range(1, max(nums or [0]) + 1)) - set(nums))
        print(f"cap{cap}: Q={len(by_cap[cap])} keypairs={len(answers.get(cap, {}))} dup={dup} gaps={gaps}")
    for kind in ("no_answer", "illegible"):
        hit = [f for f in flags if f[0] == kind]
        print(f"{kind}: {len(hit)} {hit[:40]}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--batches", required=True)
    ap.add_argument("--pages", type=int, required=True, help="number of photographed pages")
    ap.add_argument("--chapters", required=True, help="comma-separated chapter numbers to keep")
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")

    recs, missing = load_batches(args.batches, args.pages)
    target = {int(x) for x in args.chapters.split(",")}
    by_cap, answers, key_titles, flags = merge(recs, target)
    report(by_cap, answers, flags, missing)
    json.dump({"by_cap": by_cap, "answers": answers, "key_titles": key_titles,
               "missing_idx": missing, "flags": flags},
              open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("wrote", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
