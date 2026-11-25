"""Phase 4 ingest: papers -> OKF bundle, one paper at a time, in papers.yaml order.

    uv run python -m wiki.ingest --domain climate-science
    uv run python -m wiki.ingest --paper he2023 --bundle /path/to/copy

Per paper: (long papers: notes per section) -> source summary -> choose up to 5 topics ->
rewrite each topic page in full -> Python builds indexes, log, validates, commits.
The LLM writes title, description and body only.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import time
from pathlib import Path

import yaml
from langchain_core.messages import HumanMessage, SystemMessage

from common.llm import ROOT, get_chat, load_config
from common.load_pdfs import n_tokens, read_markdown_pages
from wiki.build_index import build_indexes
from wiki.okf import (BUNDLE, append_log, git_commit, papers, read_page, split_llm_output,
                      strip_broken_links, strip_defs, validate, write_page)

PROMPTS = Path(__file__).parent / "prompts"
LONG_PAPER_TOKENS = 6000  # over this, notes per section first
SECTION_TOKENS = 5000
MAX_TOPICS = 5
INGEST_SEED = load_config()["llm"]["seeds"][0]


def prompt(name: str) -> str:
    return (PROMPTS / f"{name}.md").read_text().strip()


class Ingester:
    def __init__(self, bundle: Path):
        self.bundle = bundle
        self.chat = get_chat(INGEST_SEED)
        self.calls = 0

    def call(self, step: str, system: str, user: str, pid: str, json_mode: bool = False) -> str:
        self.calls += 1
        kw = {"format": "json"} if json_mode else {}
        return self.chat.invoke(
            [SystemMessage(system), HumanMessage(user)],
            config={"metadata": {"system": "wiki", "step": step, "paper_id": pid}},
            **kw,
        ).content

    def call_parsed(self, step, system, user, pid, want_title):
        """LLM call whose output must parse as title/description/body. One retry."""
        err = ""
        for attempt in range(2):
            extra = f"\n\nYour last reply was rejected: {err}. Follow the reply format exactly." if err else ""
            raw = self.call(step, system, user + extra, pid)
            try:
                return split_llm_output(raw, want_title)
            except ValueError as e:
                err = str(e)
        return None

    # ---- bundle setup -------------------------------------------------------

    def init_bundle(self) -> None:
        self.bundle.mkdir(parents=True, exist_ok=True)
        shutil.copy(Path(__file__).parent / "bundle_agents.md", self.bundle / "AGENTS.md")
        if not (self.bundle / "log.md").exists():
            (self.bundle / "log.md").write_text("")
        build_indexes(self.bundle)
        git_commit(self.bundle, "init bundle")

    # ---- one paper ----------------------------------------------------------

    def ingest_paper(self, pid: str) -> dict:
        t0, calls0 = time.perf_counter(), self.calls
        paper = papers()[pid]
        pages = read_markdown_pages(pid)
        header = f"Paper: {paper['title']} ({paper['short_cite']}), id {pid}\n\n"

        total = sum(n_tokens(t) for _, t in pages)
        sections = split_sections(pages) if total > LONG_PAPER_TOKENS else [pages]
        if len(sections) > 1:
            notes = [
                self.call("source_notes", prompt("source_notes"), header + fmt_pages(pid, sec), pid)
                for sec in sections
            ]
            material = "Notes on the paper, in order:\n\n" + "\n\n".join(notes)
        else:
            material = fmt_pages(pid, pages)

        parsed = self.call_parsed("source_summary", prompt("source_summary"), header + material, pid, False)
        if parsed is None:
            raise RuntimeError(f"{pid}: source summary never parsed")
        _, desc, body = parsed
        src_title = f"{paper['short_cite']}: {paper['title']}"  # title is metadata from papers.yaml
        dropped = write_page(self.bundle / "sources" / f"{pid}.md", "Source Summary", src_title, desc, body)
        summary_body = strip_defs(read_page(self.bundle / "sources" / f"{pid}.md")[1])

        topics = self.select_topics(pid, summary_body)
        inputs: dict[str, str] = {}
        for slug, title in topics:
            inputs[slug] = self.write_topic(pid, slug, title, summary_body, topics)
        build_indexes(self.bundle)

        # one retry for topic pages the validator flags
        flagged = {f.path for f in validate(self.bundle)}
        for slug, _ in topics:
            rel = f"topics/{slug}.md"
            if rel in flagged:
                issues = "; ".join(f.message for f in validate(self.bundle) if f.path == rel)
                self.write_topic(pid, slug, dict(topics)[slug], summary_body, topics, retry_note=issues)
        build_indexes(self.bundle)

        # deterministic cleanup of whatever is still broken
        fixed = sum(strip_broken_links(p) for p in self.bundle.rglob("*.md") if ".git" not in p.parts)
        build_indexes(self.bundle)
        left = validate(self.bundle)

        links = f"{len(topics)} topics updated" if topics else "no topics"
        append_log(self.bundle, f"* **Ingest**: [{paper['short_cite']}](sources/{pid}.md), {links}")
        git_commit(self.bundle, f"ingest {pid}")
        rec = {
            "paper_id": pid,
            "seconds": round(time.perf_counter() - t0, 1),
            "llm_calls": self.calls - calls0,
            "topics": [s for s, _ in topics],
            "dropped_footnotes": dropped,
            "broken_links_stripped": fixed,
            "validator_left": [f"{f.path}: {f.code} {f.message}" for f in left],
        }
        with (ROOT / "runs" / "ingest_times.jsonl").open("a") as f:
            f.write(json.dumps(rec) + "\n")
        return rec

    def select_topics(self, pid: str, summary_body: str) -> list[tuple[str, str]]:
        idx = (self.bundle / "topics" / "index.md").read_text()
        user = f"Existing topic pages:\n{idx}\n\nNew paper summary ({pid}):\n{summary_body}"
        for _ in range(2):
            raw = self.call("topic_select", prompt("topic_select"), user, pid, json_mode=True)
            try:
                items = json.loads(raw)["topics"]
                out, seen = [], set()
                for it in items:
                    raw_slug = str(it["slug"]).lower().strip().rsplit("/", 1)[-1]
                    slug = re.sub(r"[^a-z0-9]+", "-", re.sub(r"\.md$", "", raw_slug)).strip("-")
                    if slug and slug not in seen and slug not in ("index", "log"):
                        seen.add(slug)
                        out.append((slug, str(it.get("title") or slug)))
                if out:
                    return out[:MAX_TOPICS]
            except (ValueError, KeyError, TypeError):
                pass
        return []

    def write_topic(self, pid, slug, title, summary_body, planned, retry_note: str = "") -> str:
        path = self.bundle / "topics" / f"{slug}.md"
        if path.exists():
            meta, body = read_page(path)
            existing = f"Existing page:\ntitle: {meta.get('title')}\n\n{strip_defs(body)}"
        else:
            existing = f"Existing page: none. Create a new page about: {title}"
        link_lines = [f"- [{t}]({s}.md)" for s, t in planned if s != slug]
        for p in sorted((self.bundle / "topics").glob("*.md")):
            if p.stem not in {s for s, _ in planned} | {slug, "index"}:
                link_lines.append(f"- [{read_page(p)[0].get('title', p.stem)}]({p.name})")
        for p in sorted((self.bundle / "sources").glob("*.md")):
            if p.name != "index.md":
                link_lines.append(f"- [{papers()[p.stem]['short_cite']}](../sources/{p.name})")
        user = (
            f"Topic slug: {slug}\nTopic title: {title}\n\n{existing}\n\n"
            f"New paper summary ({pid}):\n{summary_body}\n\n"
            "Pages you may link to (links are relative to this page):\n" + "\n".join(link_lines)
        )
        if retry_note:
            user += f"\n\nThe previous version of this page had problems: {retry_note}. Fix them."
        parsed = self.call_parsed("topic_write", prompt("topic_write"), user, pid, True)
        if parsed is None:
            print(f"  ! topic {slug}: output never parsed, left unchanged")
            return user
        t, desc, body = parsed
        write_page(path, "Topic", t or title, desc, body)
        return user


def fmt_pages(pid: str, pages: list[tuple[int, str]]) -> str:
    return "\n\n".join(f"=== {pid} page {n} (cite as [^{pid}-p{n}]) ===\n{t}" for n, t in pages)


def split_sections(pages: list[tuple[int, str]]) -> list[list[tuple[int, str]]]:
    """Page-aligned sections of about SECTION_TOKENS tokens."""
    out, cur, size = [], [], 0
    for n, t in pages:
        k = n_tokens(t)
        if cur and size + k > SECTION_TOKENS:
            out.append(cur)
            cur, size = [], 0
        cur.append((n, t))
        size += k
    if cur:
        out.append(cur)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--domain")
    ap.add_argument("--paper", action="append")
    ap.add_argument("--bundle", type=Path, default=BUNDLE)
    a = ap.parse_args()

    ids = list(papers())
    if a.paper:
        ids = a.paper
    elif a.domain:
        ids = [i for i, p in papers().items() if p["domain"] == a.domain]
    (ROOT / "runs").mkdir(exist_ok=True)
    ing = Ingester(a.bundle)
    ing.init_bundle()
    for pid in ids:
        rec = ing.ingest_paper(pid)
        print(f"{pid:<14} {rec['seconds']:>6}s {rec['llm_calls']:>2} calls topics={rec['topics']} "
              f"dropped={len(rec['dropped_footnotes'])} left={len(rec['validator_left'])}")
        for m in rec["validator_left"]:
            print("   ", m)


if __name__ == "__main__":
    main()
