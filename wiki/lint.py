"""Wiki lint (demo only): validator findings, orphan pages, LLM pass for contradictions.

    uv run python -m wiki.lint [--bundle path] [--no-llm]
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage

from common.llm import get_chat
from wiki.okf import BUNDLE, LINK, read_page, strip_defs, validate

PROMPT = (Path(__file__).parent / "prompts" / "lint.md").read_text().strip()
BATCH = 8


def pages(bundle: Path) -> list[Path]:
    return [p for p in sorted(bundle.rglob("*.md"))
            if ".git" not in p.parts and p.name not in ("index.md", "log.md", "AGENTS.md")]


def orphans(bundle: Path) -> list[str]:
    inbound: set[Path] = set()
    for p in pages(bundle):
        for _, target in LINK.findall(read_page(p)[1]):
            if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target):
                inbound.add((p.parent / target.split("#")[0]).resolve())
    return [str(p.relative_to(bundle)) for p in pages(bundle) if p.resolve() not in inbound]


def contradictions(bundle: Path) -> list[dict]:
    chat = get_chat(1)
    topics = [p for p in pages(bundle) if p.parent.name == "topics"]
    found = []
    for i in range(0, len(topics), BATCH):
        text = "\n\n".join(f"=== topics/{p.name} ===\n{strip_defs(read_page(p)[1])}" for p in topics[i:i + BATCH])
        raw = chat.invoke([SystemMessage(PROMPT), HumanMessage(text)],
                          config={"metadata": {"system": "wiki", "step": "lint"}}, format="json").content
        try:
            found += json.loads(raw)["contradictions"]
        except (ValueError, KeyError, TypeError):
            pass
    return found


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundle", type=Path, default=BUNDLE)
    ap.add_argument("--no-llm", action="store_true")
    a = ap.parse_args()
    print("validator:")
    for f in validate(a.bundle):
        print(f"  {f.path}: {f.code} {f.message}")
    print("orphans (no inbound links):", orphans(a.bundle) or "none")
    if not a.no_llm:
        for c in contradictions(a.bundle):
            print("possible contradiction:", c)
