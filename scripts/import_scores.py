"""Phase 6: validate the judge's scores and join them with the answer key.

    uv run python scripts/import_scores.py [--scores runs/scores.jsonl] [--out runs/scores_joined.csv]

scores.jsonl, one line per answer: answer_id, accuracy (correct|partial|wrong), declined (bool),
citations [{citation, supported}]. Checks every answer is scored exactly once, labels are valid, a decline
is labelled wrong unless it is flagged otherwise in the notes (warned, not fatal), and the scored citations
are the answer's citations, in order, one entry per occurrence. Then writes one CSV row per answer:
answer_id, system, question_id, seed, accuracy, declined, n_citations, n_supported.
"""
import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from common.citations import CITE  # noqa: E402

LABELS = {"correct", "partial", "wrong"}


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def validate(scores: list[dict], packets: dict[str, dict], key: dict[str, dict]) -> tuple[list[str], list[str]]:
    """Returns (errors, warnings)."""
    errors, warnings = [], []
    counts = Counter(s["answer_id"] for s in scores)
    for aid, n in counts.items():
        if n > 1:
            errors.append(f"{aid}: scored {n} times")
        if aid not in packets:
            errors.append(f"{aid}: not in judge packets")
    for aid in packets:
        if aid not in counts:
            errors.append(f"{aid}: missing from scores")
    for s in scores:
        aid = s["answer_id"]
        if s.get("accuracy") not in LABELS:
            errors.append(f"{aid}: bad accuracy {s.get('accuracy')!r}")
        if not isinstance(s.get("declined"), bool):
            errors.append(f"{aid}: declined must be true/false")
        if aid not in packets:
            continue
        actual = [f"[{p}, p.{n}]" for p, n in CITE.findall(packets[aid]["answer"])]
        given = [c.get("citation") for c in s.get("citations", [])]
        if actual != given:
            errors.append(f"{aid}: scored citations differ from answer ({len(given)} vs {len(actual)})")
        if any(not isinstance(c.get("supported"), bool) for c in s.get("citations", [])):
            errors.append(f"{aid}: citation 'supported' must be true/false")
        if s.get("declined") and s.get("accuracy") != "wrong":
            warnings.append(f"{aid}: declined but accuracy={s.get('accuracy')} (report counts it as given)")
        if aid not in key:
            errors.append(f"{aid}: not in answer_key.csv")
    return errors, warnings


def join(scores: list[dict], key: dict[str, dict]) -> list[dict]:
    rows = []
    for s in scores:
        k = key[s["answer_id"]]
        rows.append({
            "answer_id": s["answer_id"], "system": k["system"], "question_id": k["question_id"], "seed": k["seed"],
            "accuracy": s["accuracy"], "declined": int(s["declined"]),
            "n_citations": len(s["citations"]), "n_supported": sum(c["supported"] for c in s["citations"]),
        })
    return sorted(rows, key=lambda r: (r["system"], r["question_id"], r["seed"]))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scores", type=Path, default=ROOT / "runs/scores.jsonl")
    ap.add_argument("--packets", type=Path, default=ROOT / "runs/judge_packets.jsonl")
    ap.add_argument("--key", type=Path, default=ROOT / "runs/answer_key.csv")
    ap.add_argument("--out", type=Path, default=ROOT / "runs/scores_joined.csv")
    a = ap.parse_args()

    scores = load_jsonl(a.scores)
    packets = {p["answer_id"]: p for p in load_jsonl(a.packets)}
    key = {r["answer_id"]: r for r in csv.DictReader(a.key.open())}
    errors, warnings = validate(scores, packets, key)
    for w in warnings:
        print("warn:", w)
    if errors:
        sys.exit("\n".join(["errors:", *errors]))
    rows = join(scores, key)
    with a.out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} answers joined -> {a.out}")


if __name__ == "__main__":
    main()
