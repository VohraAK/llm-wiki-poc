"""Full runs: every question x both systems x every seed in config.yaml (7 x 2 x 2 = 28 answers).

    nohup uv run python scripts/full_runs.py > runs/full_runs.log 2>&1 &
    uv run python scripts/full_runs.py --dry-run

Saves runs/answers/<question-id>__<system>__s<seed>.json (the dict returned by rag.ask / wiki.query.ask:
answer, answer_raw, citation_format_fixed, citations, not_in_context, chunk_ids or pages).
Resumable: a finished answer file is skipped. A failed answer is written as {"error": ...} and retried on
the next run. Order is seed, question, system, so a stop part-way leaves both systems evenly covered.
At the end: counts, errors, and a gap check of runs/llm_log.jsonl (every answer needs a logged answer call).
Nothing is judged here, and no prompt, retrieval or config setting is touched.
"""
import argparse
import json
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from common.llm import load_config  # noqa: E402
from rag.ask import ask as rag_ask  # noqa: E402
from wiki.query import ask as wiki_ask  # noqa: E402

SYSTEMS = (("rag", rag_ask), ("wiki", wiki_ask))
OUT = ROOT / "runs" / "answers"
START = OUT / "_started_at.txt"


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def path_for(qid: str, system: str, seed: int) -> Path:
    return OUT / f"{qid}__{system}__s{seed}.json"


def done(p: Path) -> bool:
    if not p.exists():
        return False
    return "error" not in json.loads(p.read_text())


def gap_check(jobs, since: str) -> list[str]:
    """Every answer must have at least one logged step=answer call from this run, with its seed."""
    seen = set()
    for line in (ROOT / "runs" / "llm_log.jsonl").read_text().splitlines():
        r = json.loads(line)
        if r.get("step") == "answer" and r.get("at", "") >= since and r.get("ok"):
            seen.add((r.get("question_id"), r.get("system"), r.get("seed")))
    return [f"{q} {s} seed{sd}" for q, s, sd in jobs if (q, s, sd) not in seen]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only", help="only this question id (testing)")
    a = ap.parse_args()

    seeds = load_config()["llm"]["seeds"]
    questions = yaml.safe_load((ROOT / "questions/questions.yaml").read_text())["questions"]
    if a.only:
        questions = [q for q in questions if q["id"] == a.only]
    jobs = [(q["id"], s, seed) for seed in seeds for q in questions for s, _ in SYSTEMS]
    texts = {q["id"]: q["text"] for q in questions}
    fns = dict(SYSTEMS)

    print(f"{len(jobs)} answers planned ({len(questions)} questions x {len(SYSTEMS)} systems x seeds {seeds})", flush=True)
    if a.dry_run:
        for qid, s, seed in jobs:
            print(("have " if done(path_for(qid, s, seed)) else "todo ") + f"{qid} {s} seed{seed}")
        return

    OUT.mkdir(parents=True, exist_ok=True)
    if not START.exists():
        START.write_text(now())
    since = START.read_text().strip()

    t_all = time.perf_counter()
    for i, (qid, s, seed) in enumerate(jobs, 1):
        p = path_for(qid, s, seed)
        if done(p):
            print(f"[{i}/{len(jobs)}] skip {qid} {s} seed{seed}", flush=True)
            continue
        t0 = time.perf_counter()
        try:
            r = fns[s](texts[qid], seed, qid)
        except Exception:
            r = {"error": traceback.format_exc()}
        r.update({"question_id": qid, "system": s, "seed_run": seed, "seconds": round(time.perf_counter() - t0, 1)})
        p.write_text(json.dumps(r, indent=2))
        status = "ERROR" if "error" in r else f"ok not_in_context={len(r['not_in_context'])} fixed={r['citation_format_fixed']}"
        print(f"[{i}/{len(jobs)}] {qid} {s} seed{seed} {r['seconds']}s {status}", flush=True)

    files = [json.loads(path_for(*j).read_text()) for j in jobs if path_for(*j).exists()]
    errs = [f for f in files if "error" in f]
    print(f"\nanswers on disk: {len(files)}/{len(jobs)}, errors: {len(errs)}, total {round((time.perf_counter() - t_all) / 60, 1)} min")
    for s, _ in SYSTEMS:
        mine = [f for f in files if f.get("system") == s and "error" not in f]
        print(f"  {s}: {len(mine)} ok, citation_format_fixed={sum(f['citation_format_fixed'] for f in mine)}, "
              f"with_not_in_context={sum(bool(f['not_in_context']) for f in mine)}, "
              f"no_citations={sum(not f['citations'] for f in mine)}")
    gaps = gap_check(jobs, since)
    print("log gaps:", gaps or "none")
    print("DONE" if not errs and not gaps and len(files) == len(jobs) else "INCOMPLETE")


if __name__ == "__main__":
    main()
