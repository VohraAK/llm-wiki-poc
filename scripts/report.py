"""Phase 6: metrics per system (plan section 7), from runs/scores_joined.csv.

    uv run python scripts/report.py [--joined runs/scores_joined.csv] [--out runs/report.md]

Accuracy: correct / answers. Partial is its own column. A decline counts as wrong.
Citation precision: supported / all citations (answers without citations add nothing).
Cited or declined: answers with >=1 citation or a decline / all answers.
Run consistency: share of questions where seed 1 and seed 2 got the same (effective) label.
Breakdowns by tier and expected_favour are raw counts. Log stats (answer seconds, tokens in) are not analysed.
Judge agreement is read from runs/spotcheck.csv (answer_id, judge_label, hand_label) if it exists.
"""
import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SYSTEMS = ("rag", "wiki")


def effective(r: dict) -> str:
    return "wrong" if int(r["declined"]) else r["accuracy"]


def metrics(rows: list[dict]) -> dict:
    n = len(rows)
    lab = [effective(r) for r in rows]
    cites = sum(int(r["n_citations"]) for r in rows)
    sup = sum(int(r["n_supported"]) for r in rows)
    return {
        "n": n, "correct": lab.count("correct"), "partial": lab.count("partial"), "wrong": lab.count("wrong"),
        "declined": sum(int(r["declined"]) for r in rows),
        "citations": cites, "supported": sup,
        "cited_or_declined": sum(1 for r in rows if int(r["n_citations"]) > 0 or int(r["declined"])),
    }


def consistency(rows: list[dict]) -> tuple[int, int]:
    by_q = defaultdict(dict)
    for r in rows:
        by_q[r["question_id"]][int(r["seed"])] = effective(r)
    pairs = [v for v in by_q.values() if len(v) == 2]
    return sum(1 for v in pairs if v[1] == v[2]), len(pairs)


def pct(a: int, b: int) -> str:
    return f"{a}/{b} ({100 * a / b:.0f}%)" if b else "n/a"


def render(rows: list[dict], questions: dict[str, dict], logs: dict, spot: list[dict] | None) -> str:
    out = ["# Results: LLM-Wiki vs RAG", ""]
    by_sys = {s: [r for r in rows if r["system"] == s] for s in SYSTEMS}
    m = {s: metrics(by_sys[s]) for s in SYSTEMS}

    out += ["## Headline (both runs pooled)", "",
            "| System | Answers | Correct | Partial | Wrong | Declined | Citation precision | Cited or declined | Run consistency |",
            "|---|---|---|---|---|---|---|---|---|"]
    for s in SYSTEMS:
        x, (cs, cn) = m[s], consistency(by_sys[s])
        out.append(f"| {s} | {x['n']} | {pct(x['correct'], x['n'])} | {x['partial']} | {x['wrong']} | {x['declined']} | "
                   f"{pct(x['supported'], x['citations'])} | {pct(x['cited_or_declined'], x['n'])} | {pct(cs, cn)} |")

    for title, field in (("tier", "tier"), ("expected favour", "expected_favour")):
        groups = sorted({questions[r["question_id"]][field] for r in rows})
        out += ["", f"## By {title} (correct / answers; partial in brackets)", "",
                f"| {title} | " + " | ".join(SYSTEMS) + " |", "|---|" + "---|" * len(SYSTEMS)]
        for g in groups:
            cells = []
            for s in SYSTEMS:
                x = metrics([r for r in by_sys[s] if questions[r["question_id"]][field] == g])
                cells.append(f"{x['correct']}/{x['n']} ({x['partial']})")
            out.append(f"| {g} | " + " | ".join(cells) + " |")

    out += ["", "## Per question (label for seed 1 / seed 2)", "",
            "| question | " + " | ".join(SYSTEMS) + " |", "|---|" + "---|" * len(SYSTEMS)]
    for q in sorted({r["question_id"] for r in rows}):
        cells = []
        for s in SYSTEMS:
            labs = {int(r["seed"]): effective(r) for r in by_sys[s] if r["question_id"] == q}
            cells.append(" / ".join(labs.get(k, "-") for k in (1, 2)))
        out.append(f"| {q} | " + " | ".join(cells) + " |")

    if logs:
        out += ["", "## From the logs (not analysed)", "", "| System | mean answer seconds | mean tokens in | mean tokens out |", "|---|---|---|---|"]
        for s in SYSTEMS:
            l = logs.get(s)
            if l:
                out.append(f"| {s} | {l['seconds']:.1f} | {l['tokens_in']:.0f} | {l['tokens_out']:.0f} |")

    out += ["", "## Judge agreement (hand spot-check)", ""]
    if spot:
        agree = sum(1 for r in spot if r["judge_label"] == r["hand_label"])
        out.append(f"Judge and hand label agree on {agree}/{len(spot)} answers.")
    else:
        out.append("Not done: no hand spot-check was run. Labels are one Claude judge pass and are unverified. See NOTES.md.")
    return "\n".join(out) + "\n"


def read_logs() -> dict:
    """Mean answer seconds (answer files) and tokens (last llm_log answer call per system/question/seed)."""
    secs = defaultdict(list)
    for p in (ROOT / "runs/answers").glob("*.json"):
        d = json.loads(p.read_text())
        secs[d["system"]].append(d["seconds"])
    last = {}
    log = ROOT / "runs/llm_log.jsonl"
    if log.exists():
        for line in log.read_text().splitlines():
            d = json.loads(line)
            if d.get("step") == "answer" and d.get("question_id") and d.get("ok"):
                last[(d["system"], d["question_id"], d["seed"])] = d
    out = {}
    for s in SYSTEMS:
        t = [v for k, v in last.items() if k[0] == s]
        if secs[s] and t:
            out[s] = {"seconds": sum(secs[s]) / len(secs[s]),
                      "tokens_in": sum(x["tokens_in"] for x in t) / len(t),
                      "tokens_out": sum(x["tokens_out"] for x in t) / len(t)}
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--joined", type=Path, default=ROOT / "runs/scores_joined.csv")
    ap.add_argument("--out", type=Path, default=ROOT / "runs/report.md")
    ap.add_argument("--no-logs", action="store_true")
    a = ap.parse_args()
    rows = list(csv.DictReader(a.joined.open()))
    questions = {q["id"]: q for q in yaml.safe_load((ROOT / "questions/questions.yaml").read_text())["questions"]}
    spot_path = ROOT / "runs/spotcheck.csv"
    spot = list(csv.DictReader(spot_path.open())) if spot_path.exists() else None
    text = render(rows, questions, {} if a.no_logs else read_logs(), spot)
    a.out.write_text(text)
    sys.stdout.write(text)


if __name__ == "__main__":
    main()
