"""Wiki query, fixed two steps (no agent loop).

    uv run python -m wiki.query "question" --seed 1

1. The LLM reads the root, sources/ and topics/ indexes plus the question and picks up to 6 pages.
2. Python loads those pages (footnote labels turned into [<paper-id>, p.<N>]) and the LLM answers
   with the shared answer rules.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage

from common.citations import check_citations, normalize_citations
from common.llm import get_chat
from common.prompts import ANSWER_PROMPT
from wiki.okf import BUNDLE, FOOT, LABEL, label_to_citation, read_page, strip_defs, valid_label

MAX_PAGES = 6
SELECT_PROMPT = (Path(__file__).parent / "prompts" / "query_select.md").read_text().strip()


def index_text(bundle: Path) -> str:
    """Root, sources/ and topics/ indexes, with link targets written as bundle paths."""
    parts = []
    for rel in ("index.md", "sources/index.md", "topics/index.md"):
        text = (bundle / rel).read_text()
        folder = rel.rsplit("/", 1)[0] + "/" if "/" in rel else ""
        if folder:
            text = re.sub(r"\]\(([^)/]+\.md)\)", lambda m: f"]({folder}{m.group(1)})", text)
        parts.append(f"=== {rel} ===\n{text.strip()}")
    return "\n\n".join(parts)


def select_pages(chat, bundle: Path, question: str, meta: dict) -> list[str]:
    raw = chat.invoke(
        [SystemMessage(SELECT_PROMPT), HumanMessage(f"{index_text(bundle)}\n\nQuestion: {question}")],
        config={"metadata": {**meta, "step": "select"}},
        format="json",
    ).content
    try:
        pages = json.loads(raw)["pages"]
    except (ValueError, KeyError, TypeError):
        return []
    out = []
    for p in pages:
        p = str(p).strip().lstrip("/")
        f = bundle / p
        if p.endswith(".md") and not p.endswith("index.md") and f.is_file() and p not in out:
            out.append(p)
    return out[:MAX_PAGES]


def render_page(bundle: Path, rel: str) -> tuple[str, set[tuple[str, int]]]:
    meta, body = read_page(bundle / rel)
    body = FOOT.sub(lambda m: label_to_citation(m.group(1)) if valid_label(m.group(1)) else "", strip_defs(body))
    shown = {(m.group(1), int(m.group(2))) for m in re.finditer(r"\[([a-z]+\d{4}), p\.(\d+)\]", body)}
    return f"=== wiki page {rel}: {meta.get('title', '')} ===\n{body}", shown


def ask(question: str, seed: int, question_id: str | None = None, bundle: Path = BUNDLE) -> dict:
    chat = get_chat(seed)
    meta = {"system": "wiki", "question_id": question_id}
    pages = select_pages(chat, bundle, question, meta)
    rendered, shown = [], set()
    for rel in pages:
        text, s = render_page(bundle, rel)
        rendered.append(text)
        shown |= s
    msgs = ANSWER_PROMPT.invoke({"context": "\n\n".join(rendered), "question": question})
    raw = chat.invoke(msgs, config={"metadata": {**meta, "step": "answer"}}).content
    answer, fixed = normalize_citations(raw)
    return {"question": question, "seed": seed, "answer": answer, "answer_raw": raw,
            "citation_format_fixed": fixed, "pages": pages, **check_citations(answer, shown)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("question")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--bundle", type=Path, default=BUNDLE)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    r = ask(a.question, a.seed, bundle=a.bundle)
    if a.json:
        print(json.dumps(r, indent=2))
    else:
        print(r["answer"])
        print("\npages:", ", ".join(r["pages"]))
        print("citations:", r["citations"])
        print("not in loaded pages:", r["not_in_context"] or "none")
