"""    uv run python -m rag.ask "question" --seed 1"""
from __future__ import annotations

import argparse
import json

from common.citations import check_citations, normalize_citations
from rag.graph import build_graph


def ask(question: str, seed: int, question_id: str | None = None) -> dict:
    out = build_graph(seed, question_id).invoke({"question": question})
    raw = out["answer"]
    answer, fixed = normalize_citations(raw)
    docs = out["context"]
    chunk_ids = [d.metadata["chunk_id"] for d in docs]
    shown = {(d.metadata["paper_id"], d.metadata["page"]) for d in docs}
    return {
        "question": question,
        "seed": seed,
        "answer": answer,
        "answer_raw": raw,
        "citation_format_fixed": fixed,
        "chunk_ids": chunk_ids,
        **check_citations(answer, shown),
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("question")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    r = ask(a.question, a.seed)
    if a.json:
        print(json.dumps(r, indent=2))
    else:
        print(r["answer"])
        print("\nchunks:", ", ".join(r["chunk_ids"]))
        print("citations:", r["citations"])
        print("not in retrieved context:", r["not_in_context"] or "none")
