import json
import os
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "pipeline"))

import audit_fix  # noqa: E402
import build_quiz  # noqa: E402
import merge_ocr  # noqa: E402


def one_question(answer, fix):
    return {"chapters": [{"num": 1, "questions": [
        {"num": "1", "stem": "Următoarele afirmații sunt false, cu EXCEPȚIA:", "answer": answer, "fix": fix}]}]}


def test_audit_accepts_fix_that_confirms_the_key():
    data = one_question("C", "A — arterele duc sângele de la inimă.\nC — adevărată: aceasta este excepția.")
    assert audit_fix.audit(data) == []


def test_audit_flags_line_that_argues_the_keyed_letter_is_false():
    # shape 1, the real bug: the fix "corrected" the one statement that was true
    data = one_question("A", "A — glandele sublinguale NU sunt în fața celor submandibulare.")
    hits = audit_fix.audit(data)
    assert len(hits) == 1 and "argues it FALSE" in hits[0][3][0]


def test_audit_flags_fix_that_crowns_another_letter():
    # shape 2: the fix ends by naming a different correct answer than the key
    data = one_question("A", "B — ...\n(E corect: parotida este superficială)")
    hits = audit_fix.audit(data)
    assert any("crowns E correct" in r for r in hits[0][3])


def test_audit_skips_questions_without_fix():
    assert audit_fix.audit(one_question("B", "")) == []


def test_build_joins_enrichment_and_fills_template(tmp_path):
    out = tmp_path / "quiz.html"
    assert build_quiz.main(["--data", os.path.join(ROOT, "sample"), "--out", str(out),
                            "--title", "Demo", "--storage-key", "k"]) == 0
    html = out.read_text(encoding="utf-8")
    assert "{{TITLE}}" not in html and "{{STORAGE_KEY}}" not in html
    data = json.loads((tmp_path / "quiz_data.json").read_text(encoding="utf-8"))
    qs = data["chapters"][0]["questions"]
    assert len(qs) == 4
    assert [q["excluded"] for q in qs] == [False, False, False, True]
    assert qs[0]["fix"].startswith("Valva mitrală")
    assert audit_fix.audit(data) == []


def test_merge_carries_chapter_forward_and_joins_key():
    recs = {
        0: {"idx": 0, "chapter_header": {"cap": 3, "title": "Celula"},
            "questions": [{"num": 1, "stem": "S1", "options": {"A": "x"}}]},
        # page without a header still belongs to chapter 3
        1: {"idx": 1, "questions": [{"num": 2, "stem": "S2 [?]", "options": {"A": "y"}}]},
        2: {"idx": 2, "key_tables": [{"cap": 3, "answers": {"1": "A"}}]},
    }
    by_cap, answers, _, flags = merge_ocr.merge(recs, {3})
    assert [q["num"] for q in by_cap[3]] == [1, 2]
    assert by_cap[3][0]["answer"] == "A"
    assert ("illegible", 3, 2, 1) in flags
    assert ("no_answer", 3, 2, None) in flags
