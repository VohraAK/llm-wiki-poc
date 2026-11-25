"""Hand-computed checks for scripts/import_scores.py and scripts/report.py.  uv run python tests/test_report.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import import_scores as imp  # noqa: E402
import report as rep  # noqa: E402


def row(system, q, seed, acc, declined=0, n=0, sup=0):
    return {"answer_id": f"{system}{q}{seed}", "system": system, "question_id": q, "seed": str(seed),
            "accuracy": acc, "declined": str(declined), "n_citations": str(n), "n_supported": str(sup)}


rows = [
    row("rag", "q1", 1, "correct", 0, 4, 3), row("rag", "q1", 2, "correct", 0, 2, 2),
    row("rag", "q2", 1, "partial", 0, 0, 0), row("rag", "q2", 2, "correct", 1, 0, 0),  # decline overrides label
    row("wiki", "q1", 1, "wrong", 0, 5, 1), row("wiki", "q1", 2, "wrong", 0, 5, 4),
    row("wiki", "q2", 1, "partial", 0, 1, 1), row("wiki", "q2", 2, "partial", 0, 1, 0),
]
R = [r for r in rows if r["system"] == "rag"]
m = rep.metrics(R)
assert (m["n"], m["correct"], m["partial"], m["wrong"], m["declined"]) == (4, 2, 1, 1, 1), m
assert (m["citations"], m["supported"]) == (6, 5), m
assert m["cited_or_declined"] == 3, m          # q1 s1, q1 s2, the decline; the uncited partial adds nothing
assert rep.consistency(R) == (1, 2)            # q1 same, q2 partial vs wrong(decline)
W = [r for r in rows if r["system"] == "wiki"]
assert rep.consistency(W) == (2, 2)
assert rep.metrics(W)["supported"] == 6 and rep.metrics(W)["citations"] == 12
assert rep.pct(0, 0) == "n/a"
qs = {"q1": {"tier": "a", "expected_favour": "rag"}, "q2": {"tier": "b", "expected_favour": "wiki"}}
text = rep.render(rows, qs, {}, None)
assert "| rag | 4 | 2/4 (50%) | 1 | 1 | 1 | 5/6 (83%) | 3/4 (75%) | 1/2 (50%) |" in text, text
assert "| a | 2/2 (0) | 0/2 (0) |" in text and "| b | 0/2 (1) | 0/2 (2) |" in text, text

# validation
packets = {"x": {"answer": "Yes [he2023, p.1][he2023, p.4]."}, "y": {"answer": "No cites."}}
key = {"x": {"system": "rag", "question_id": "q1", "seed": "1"}, "y": {"system": "wiki", "question_id": "q1", "seed": "1"}}
good = [{"answer_id": "x", "accuracy": "correct", "declined": False,
         "citations": [{"citation": "[he2023, p.1]", "supported": True}, {"citation": "[he2023, p.4]", "supported": False}]},
        {"answer_id": "y", "accuracy": "wrong", "declined": True, "citations": []}]
assert imp.validate(good, packets, key) == ([], [])
bad = [{"answer_id": "x", "accuracy": "great", "declined": False, "citations": [{"citation": "[he2023, p.1]", "supported": True}]},
       {"answer_id": "z", "accuracy": "wrong", "declined": True, "citations": []}]
errs, _ = imp.validate(bad, packets, key)
joined = " | ".join(errs)
for needle in ("bad accuracy", "differ from answer", "z: not in judge packets", "y: missing from scores"):
    assert needle in joined, (needle, joined)
dup = good + [good[0]]
assert any("scored 2 times" in e for e in imp.validate(dup, packets, key)[0])
_, warns = imp.validate([{**good[1], "accuracy": "partial"}, good[0]], packets, key)
assert warns and "declined but accuracy=partial" in warns[0]
print("ok")
