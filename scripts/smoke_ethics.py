"""Pre-freeze smoke test: T1 and B3 (ethics) through both systems, seed 1. Saves runs/smoke/*.json. Not judged."""
import json, sys, traceback
from pathlib import Path
import yaml
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from rag.ask import ask as rag_ask
from wiki.query import ask as wiki_ask
out = ROOT / "runs" / "smoke"; out.mkdir(parents=True, exist_ok=True)
qs = {q["id"]: q for q in yaml.safe_load((ROOT / "questions/questions.yaml").read_text())["questions"]}
for qid in ["T1-mia-evolution", "B3-mia-attack-success-rate"]:
    for name, fn in (("rag", rag_ask), ("wiki", wiki_ask)):
        try: r = fn(qs[qid]["text"], 1, qid)
        except Exception: r = {"error": traceback.format_exc()}
        (out / f"{qid}__{name}.json").write_text(json.dumps(r, indent=2))
        print(qid, name, "ERROR" if "error" in r else "ok", flush=True)
