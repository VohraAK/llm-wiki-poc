"""Pilot: T2-oae, T4, B2 through both systems, seed 1. Saves runs/pilot/<qid>__<system>.json.

    uv run python scripts/pilot.py
Nothing is judged here. Failures are recorded and the run continues.
"""
import json
import sys
import traceback
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from rag.ask import ask as rag_ask  # noqa: E402
from wiki.query import ask as wiki_ask  # noqa: E402

IDS = ["T2-oae-bio-vs-chemical", "T4-eelgrass-mrv-gaps", "B2-he-tyka-equilibration-ratios"]
out = ROOT / "runs" / "pilot"
out.mkdir(parents=True, exist_ok=True)
qs = {q["id"]: q for q in yaml.safe_load((ROOT / "questions/questions.yaml").read_text())["questions"]}

for qid in IDS:
    for name, fn in (("rag", rag_ask), ("wiki", wiki_ask)):
        try:
            r = fn(qs[qid]["text"], 1, qid)
        except Exception:
            r = {"error": traceback.format_exc()}
        (out / f"{qid}__{name}.json").write_text(json.dumps(r, indent=2))
        print(qid, name, "ERROR" if "error" in r else f"ok, not_in_context={r.get('not_in_context')}", flush=True)
