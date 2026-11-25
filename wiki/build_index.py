"""Regenerate the index.md files from page frontmatter.

    uv run python -m wiki.build_index [bundle]

Folder indexes have no frontmatter. The root index keeps its frontmatter.
"""
from __future__ import annotations

import sys
from pathlib import Path

from wiki.okf import BUNDLE, papers, read_page

ROOT_FM = """---
okf_version: "0.3"
title: LLM-Wiki PoC, ocean alkalinity enhancement and AI ethics and copyright
description: A wiki compiled by an LLM from 16 research papers, with one summary page per paper and topic pages that connect them.
---
"""


def _line(path: Path) -> str:
    meta, _ = read_page(path)
    desc = " ".join(str(meta.get("description", "")).split())
    return f"* [{meta.get('title', path.stem)}]({path.name}) - {desc}"


def build_indexes(bundle: Path = BUNDLE) -> None:
    (bundle / "sources").mkdir(parents=True, exist_ok=True)
    (bundle / "topics").mkdir(parents=True, exist_ok=True)

    order = {pid: i for i, pid in enumerate(papers())}
    src = sorted(
        (p for p in (bundle / "sources").glob("*.md") if p.name != "index.md"),
        key=lambda p: order.get(p.stem, 999),
    )
    (bundle / "sources" / "index.md").write_text("# Sources\n\n" + "\n".join(_line(p) for p in src) + "\n")

    topics = sorted(
        (p for p in (bundle / "topics").glob("*.md") if p.name != "index.md"),
        key=lambda p: str(read_page(p)[0].get("title", p.stem)).lower(),
    )
    (bundle / "topics" / "index.md").write_text("# Topics\n\n" + "\n".join(_line(p) for p in topics) + "\n")

    root = bundle / "index.md"
    fm = ROOT_FM
    if root.exists() and root.read_text().startswith("---"):
        fm = root.read_text().split("\n---\n", 1)[0] + "\n---\n"
    root.write_text(
        fm
        + "\n* [Sources](sources/index.md) - one summary page per paper\n"
        + "* [Topics](topics/index.md) - concepts, methods, findings and debates that span papers\n"
    )


if __name__ == "__main__":
    build_indexes(Path(sys.argv[1]) if len(sys.argv) > 1 else BUNDLE)
