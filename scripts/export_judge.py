"""Phase 6: export blinded judge packets from runs/answers/.

    uv run python scripts/export_judge.py [--force]

Writes
  runs/judge_packets.jsonl  one line per answer, shuffled: answer_id (random), question, reference_key_points,
                            caveats, answer (citations already normalised), cited_pages
  runs/answer_key.csv       answer_id -> system, question_id, seed. Keep it away from the judge.

Packets carry only those fields. Nothing from the run files that differs by system (answer_raw,
citation_format_fixed, chunk ids, wiki page names, timings) is copied. Answer text is NOT edited here beyond
the citation normalisation done at answer time, so style differences stay. They are counted below and
belong in the disclosed limitations. Refuses to overwrite existing packets unless --force, because the
key and any scores are tied to the ids.
"""
import argparse
import csv
import json
import random
import re
import secrets
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from common.citations import extract_citations  # noqa: E402
from common.load_pdfs import read_markdown_pages  # noqa: E402

ANSWERS = ROOT / "runs" / "answers"
PACKETS = ROOT / "runs" / "judge_packets.jsonl"
KEY = ROOT / "runs" / "answer_key.csv"

# Strings that could tell the judge which system wrote an answer. Counted, not removed.
TELLS = {
    "latex": re.compile(r"\$[^$\n]+\$|\\text\{|\\Delta"),
    "wiki_words": re.compile(r"\bwiki\b|\bsources/|\btopics/|\.md\b", re.I),
    "rag_words": re.compile(r"\bchunk", re.I),
    "does_not_contain": re.compile(r"does not contain|documents don't cover", re.I),
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    if (PACKETS.exists() or KEY.exists()) and not a.force:
        sys.exit(f"{PACKETS.name} or {KEY.name} already exists. Ids are tied to scores. Use --force to overwrite.")

    questions = {q["id"]: q for q in yaml.safe_load((ROOT / "questions/questions.yaml").read_text())["questions"]}
    page_cache: dict[str, dict[int, str]] = {}

    def page_text(pid: str, n: int):
        if pid not in page_cache:
            try:
                page_cache[pid] = dict(read_markdown_pages(pid))
            except Exception:
                page_cache[pid] = {}
        return page_cache[pid].get(n)

    files = sorted(ANSWERS.glob("*__s*.json"))
    rows = []
    for f in files:
        r = json.loads(f.read_text())
        if "error" in r:
            sys.exit(f"{f.name} is an error result. Rerun scripts/full_runs.py first.")
        q = questions[r["question_id"]]
        cites = extract_citations(r["answer"])
        rows.append({
            "system": r["system"], "question_id": r["question_id"], "seed": r["seed_run"],
            "packet": {
                "question": q["text"].strip(),
                "reference_key_points": q["reference_key_points"],
                "caveats": q.get("caveats") or [],
                "answer": r["answer"],
                "cited_pages": [
                    {"citation": f"[{pid}, p.{n}]", "text": page_text(pid, n)} for pid, n in cites
                ],
            },
        })

    # unique random ids, then shuffle (fixed shuffle seed only so a --force rerun is reproducible apart from ids)
    ids: set[str] = set()
    for row in rows:
        while True:
            i = "a" + secrets.token_hex(4)
            if i not in ids:
                ids.add(i)
                row["answer_id"] = i
                break
    random.Random(20261125).shuffle(rows)

    with PACKETS.open("w") as out:
        for row in rows:
            out.write(json.dumps({"answer_id": row["answer_id"], **row["packet"]}) + "\n")
    with KEY.open("w", newline="") as out:
        w = csv.writer(out)
        w.writerow(["answer_id", "system", "question_id", "seed"])
        for row in rows:
            w.writerow([row["answer_id"], row["system"], row["question_id"], row["seed"]])

    print(f"{len(rows)} packets -> {PACKETS.relative_to(ROOT)}, key -> {KEY.relative_to(ROOT)}")
    missing = [(r["answer_id"], c["citation"]) for r in rows for c in r["packet"]["cited_pages"] if c["text"] is None]
    print("cited pages not found in data/md:", missing or "none")
    print("\nstyle tells in answer text (answers containing each), by system:")
    for name, rx in TELLS.items():
        counts = {s: sum(bool(rx.search(r["packet"]["answer"])) for r in rows if r["system"] == s) for s in ("rag", "wiki")}
        print(f"  {name:<17} rag={counts['rag']:>2}  wiki={counts['wiki']:>2}")
    for s in ("rag", "wiki"):
        lens = [len(r["packet"]["answer"].split()) for r in rows if r["system"] == s]
        print(f"  mean words {s}: {sum(lens) / len(lens):.0f}")


if __name__ == "__main__":
    main()
